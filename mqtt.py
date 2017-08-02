# mqtt.py MQTT library for the micropython board using an ESP8266.
# asyncio version

# Author: Peter Hinch
# Copyright Peter Hinch 2017 Released under the MIT license

# Accessed via pbmqtt.py on Pyboard

import gc
import ubinascii
from mqtt_as import MQTTClient
from machine import Pin, unique_id, freq
import uasyncio as asyncio
gc.collect()
from network import WLAN, STA_IF, AP_IF
gc.collect()
from syncom import SynCom
gc.collect()
import ntptime
gc.collect()
from status_values import *  # Numeric status values shared with user code.

_WIFI_DELAY = 15  # Time (s) to wait for default network

# Format an arbitrary list of positional args as a comma separated string
def argformat(*a):
    return ','.join(['{}' for x in range(len(a))]).format(*a)

async def heartbeat():
    led = Pin(0, Pin.OUT)
    while True:
        await asyncio.sleep_ms(500)
        led(not led())


class Client(MQTTClient):
    lw_parms = None
    @classmethod
    def will(cls, parms):
        cls.lw_parms = parms

    def __init__(self, config, channel, client_id, server, t_resync, port, user,
                 password, keepalive, ssl, ssl_params):
        self.channel = channel
        self.t_resync = t_resync
        self.subscriptions = {}
        config['subs_cb'] = self.subs_cb
        config['wifi_coro'] = self.wifi_han
        config['connect_coro'] = self.conn_han
        if self.lw_parms is not None:
            config['will'] = (self.lw_parms[0], self.lw_parms[1],
                              bool(self.lw_parms[2]), int(self.lw_parms[3]))
        super().__init__(config, client_id, server, port=port, user=user,
                         password=password, keepalive=keepalive, ssl=ssl,
                         ssl_params=ssl_params)

    # If t_resync > 0, at intervals get time from timeserver, send time to channel
    # If t_resync < 0 synchronise once only.
    # If t_rsync == 0 no synch (task never runs)
    async def rtc_task(self):
        while self.isconnected():
            try:
                t = ntptime.time()  # secs since Y2K
            except OSError:
                t = 0
                await asyncio.sleep(30)
            if t > 16 * 365 * 24 * 3600:
                self.channel.send(argformat('time', t))
                if self.t_resync > 0:
                    await asyncio.sleep(self.t_resync)
                else:
                    await asyncio.sleep(0)
                    return
            else:
                await asyncio.sleep(30)

    async def wifi_han(self, state):
        if state:
            self.channel.send(argformat('status', WIFI_UP))
        else:
            self.channel.send(argformat('status', WIFI_DOWN))
        await asyncio.sleep(1)

    async def conn_han(self, _):
        if self.t_resync:
            loop = asyncio.get_event_loop()
            loop.create_task(self.rtc_task())
        for topic, qos in self.subscriptions.items():
            await client.subscribe(topic, qos)

    def subs_cb(self, topic, msg):
        self.channel.send(argformat('subs', topic.decode('UTF8'), msg.decode('UTF8')))

class Channel(SynCom):
    def __init__(self):
        mtx = Pin(14, Pin.OUT)              # Define pins
        mckout = Pin(15, Pin.OUT, value=0)  # clocks must be initialised to 0
        mrx = Pin(13, Pin.IN)
        mckin = Pin(12, Pin.IN)
        super().__init__(True, mckin, mckout, mrx, mtx, string_mode = True)
        self.cstatus = False  # Connection status
        self.client = None

# Task runs continuously. Process incoming Pyboard messages.
# Started by main_task() after client instantiated.
    async def from_pyboard(self):
        client = self.client
        while True:
            istr = await self.await_obj(100)  # wait for string (poll interval 100ms)
            s = istr.split(',')
            command = s[0]
            if command == 'publish':
                await client.publish(s[1], s[2], bool(s[3]), int(s[4]))
                # If qos == 1 only returns once PUBACK received.
                self.send(argformat('status', PUBOK))
            elif command == 'subscribe':
                await client.subscribe(s[1], int(s[2]))
                client.subscriptions[s[1]] = int(s[2])  # re-subscribe after outage
            elif command == 'mem':
                gc.collect()
                gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
                self.send(argformat('mem', gc.mem_free(), gc.mem_alloc()))
            else:
                self.send(argformat('status', UNKNOWN, 'Unknown command:', ostr))

# Runs when channel has synchronised. No return: Pyboard resets ESP on fail.
# Get parameters from Pyboard. Process them. Connect. Instantiate client. Start
# from_pyboard() task. Wait forever, updating connected status.
    async def main_task(self, _):
        config = {}  # Possible enhancement: init to be capable of clearing clean
        got_params = False

        # Await connection parameters (init record)
        while not got_params:
            istr = await self.await_obj(100)
            ilst = istr.split(',')
            command = ilst[0]
            if command == 'init':
                got_params = True
                ssid, pw, broker, m_user, m_pw, ssl_params = ilst[1:7]
                use_default, port, ssl, fast, t_resync, keepalive = [int(x) for x in ilst[7:]]
                m_user = m_user if m_user else None
                m_pw = m_pw if m_pw else None
            elif command == 'will':
                Client.will(ilst[1:5])
                self.send(argformat('status', WILLOK))
            else:
                self.send(argformat('status', UNKNOWN, 'Expected init, got: ', istr))

        # Got parameters
        if fast:
            freq(160000000)

        # try default LAN if required
        sta_if = WLAN(STA_IF)
        if use_default:
            self.send(argformat('status', DEFNET))
            secs = _WIFI_DELAY
            while secs >= 0 and not sta_if.isconnected():
                await asyncio.sleep(1)
                secs -= 1

        # If can't use default, use specified LAN
        if not sta_if.isconnected():
            self.send(argformat('status', SPECNET))
            # Pause for confirmation. User may opt to reboot instead.
            istr = await self.await_obj(100)
            ap = WLAN(AP_IF) # create access-point interface
            ap.active(False)         # deactivate the interface
            sta_if.active(True)
            sta_if.connect(ssid, pw)
            while not sta_if.isconnected():
                await asyncio.sleep(1)

        # WiFi is up: connect to the broker
        await asyncio.sleep(5)  # Let WiFi stabilise before connecting
        client_id = ubinascii.hexlify(unique_id())
        self.client = Client(config, self, client_id, broker, t_resync, port,
                                m_user, m_pw, keepalive, ssl, eval(ssl_params))
        self.send(argformat('status', BROKER_CHECK))
        try:
            await self.client.connect()  # Clean session. Throws OSError if broker down.
            # Sends BROKER_OK and RUNNING
        except OSError:
            # Cause Pyboard to reboot us when application requires it.
            self.send(argformat('status', BROKER_FAIL))
            while True:
                await asyncio.sleep(60)  # Twiddle my thumbs. PB will reset me.

        self.send(argformat('status', BROKER_OK))
        self.send(argformat('status', RUNNING))
        # Set channel running
        loop = asyncio.get_event_loop()
        loop.create_task(self.from_pyboard())
        while True:
            gc.collect()
            gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
            await asyncio.sleep(1)

loop = asyncio.get_event_loop()
loop.create_task(heartbeat())
# Comms channel to Pyboard
channel = Channel()
loop.create_task(channel.start(channel.main_task))
loop.run_forever()
