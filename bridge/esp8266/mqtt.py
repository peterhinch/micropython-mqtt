# mqtt.py MQTT library for the micropython board using an ESP8266.
# asyncio version

# Author: Peter Hinch
# Copyright Peter Hinch 2017-2021 Released under the MIT license

# Accessed via pbmqtt.py on Pyboard

import gc
import ubinascii
from mqtt_as import MQTTClient, config
from machine import Pin, unique_id, freq
import uasyncio as asyncio
gc.collect()
from network import WLAN, STA_IF, AP_IF
import usocket as socket
gc.collect()
from syncom import SynCom
gc.collect()
import ustruct as struct
from status_values import *  # Numeric status values shared with user code.

_WIFI_DELAY = 15  # Time (s) to wait for default network
blue = Pin(2, Pin.OUT, value = 1)

# Format an arbitrary list of positional args as a status_values.SEP separated string
def argformat(*a):
    return SEP.join(['{}' for x in range(len(a))]).format(*a)

async def heartbeat():
    led = Pin(0, Pin.OUT)
    while True:
        await asyncio.sleep_ms(500)
        led(not led())


class Client(MQTTClient):
    def __init__(self, channel, config):
        self.channel = channel
        self.subscriptions = {}
        # Config defaults:
        # 4 repubs, delay of 10 secs between (response_time).
        # Initially clean session.
        config['subs_cb'] = self.subs_cb
        config['wifi_coro'] = self.wifi_han
        config['connect_coro'] = self.conn_han
        config['client_id'] = ubinascii.hexlify(unique_id())
        self.timeserver = config['timeserver']
        super().__init__(config)

    # Get NTP time or 0 on any error.
    async def get_time(self):
        if not self.isconnected():
            return 0
        res = await self.wan_ok()
        if not res:
            return 0  # No internet connectivity.
        # connectivity check is not ideal. Could fail now... FIXME
        # (date(2000, 1, 1) - date(1900, 1, 1)).days * 24*60*60
        NTP_DELTA = 3155673600
        host = self.timeserver
        NTP_QUERY = bytearray(48)
        NTP_QUERY[0] = 0x1b
        t = 0
        async with self.lock:
            addr = socket.getaddrinfo(host, 123)[0][-1]  # Blocks 15s if no internet
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setblocking(False)
            try:
                s.connect(addr)
                await self._as_write(NTP_QUERY, 48, s)
                await asyncio.sleep(2)
                msg = await self._as_read(48, s)
                val = struct.unpack("!I", msg[40:44])[0]
                t = val - NTP_DELTA
            except OSError:
                pass
            s.close()

        if t < 16 * 365 * 24 * 3600:
            t = 0
        self.dprint('Time received: ', t, ' from:', host)
        return t

    async def wifi_han(self, state):
        if state:
            self.channel.send(argformat(STATUS, WIFI_UP))
        else:
            self.channel.send(argformat(STATUS, WIFI_DOWN))
        blue(not state)
        await asyncio.sleep(1)

    async def conn_han(self, _):
        for topic, qos in self.subscriptions.items():
            await self.subscribe(topic, qos)

    def subs_cb(self, topic, msg, retained):
        self.channel.send(argformat(SUBSCRIPTION, topic.decode('UTF8'), msg.decode('UTF8'), retained))

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
            istr = await self.await_obj(20)  # wait for string (poll interval 20ms)
            s = istr.split(SEP)
            command = s[0]
            if command == PUBLISH:
                await client.publish(s[1], s[2], bool(s[3]), int(s[4]))
                # If qos == 1 only returns once PUBACK received.
                self.send(argformat(STATUS, PUBOK))
            elif command == SUBSCRIBE:
                await client.subscribe(s[1], int(s[2]))
                client.subscriptions[s[1]] = int(s[2])  # re-subscribe after outage
            elif command == MEM:
                gc.collect()
                gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
                self.send(argformat(MEM, gc.mem_free(), gc.mem_alloc()))
            elif command == TIME:
                t = await client.get_time()
                self.send(argformat(TIME, t))
            else:
                self.send(argformat(STATUS, UNKNOWN, 'Unknown command:', istr))

# Runs when channel has synchronised. No return: Pyboard resets ESP on fail.
# Get parameters from Pyboard. Process them. Connect. Instantiate client. Start
# from_pyboard() task. Wait forever, updating connected status.
    async def main_task(self, _):
        got_params = False
        # Await connection parameters (init record)
        while not got_params:
            istr = await self.await_obj(100)
            ilst = istr.split(SEP)
            command = ilst[0]
            if command == 'init':
                got_params = True
                ssid, pw, broker, mqtt_user, mqtt_pw, ssl_params = ilst[1:7]
                use_default = bool(int(ilst[7]))
                fast = bool(int(ilst[10]))
                debug = bool(int(ilst[12]))
                config['server'] = broker
                config['port'] = int(ilst[8])
                config['user'] = mqtt_user
                config['password'] = mqtt_pw
                config['keepalive'] = int(ilst[11])
                config['ping_interval'] = int(ilst[16])
                config['ssl'] = bool(int(ilst[9]))
                config['ssl_params'] = eval(ssl_params)
                config['response_time'] = int(ilst[15])
                config['clean'] = bool(int(ilst[13]))
                config['max_repubs'] = int(ilst[14])
                config['timeserver'] = ilst[17]
            elif command == WILL:
                config['will'] = (ilst[1:3] + [bool(ilst[3])] + [int(ilst[4])])
                self.send(argformat(STATUS, WILLOK))
            else:
                self.send(argformat(STATUS, UNKNOWN, 'Expected init, got: ', istr))
        # Got parameters
        if debug:
            Client.DEBUG = True  # verbose output on UART

        if fast:
            freq(160000000)

        # try default LAN if required
        sta_if = WLAN(STA_IF)
        if use_default:
            self.send(argformat(STATUS, DEFNET))
            secs = _WIFI_DELAY
            while secs >= 0 and not sta_if.isconnected():
                await asyncio.sleep(1)
                secs -= 1

        # If can't use default, use specified LAN
        if not sta_if.isconnected():
            self.send(argformat(STATUS, SPECNET))
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
        self.client = Client(self, config)
        self.send(argformat(STATUS, BROKER_CHECK))
        try:
            await self.client.connect()  # Clean session. Throws OSError if broker down.
            # Sends BROKER_OK and RUNNING
        except OSError:
            # Cause Pyboard to reboot us when application requires it.
            self.send(argformat(STATUS, BROKER_FAIL))
            while True:
                await asyncio.sleep(60)  # Twiddle my thumbs. PB will reset me.

        self.send(argformat(STATUS, BROKER_OK))
        self.send(argformat(STATUS, RUNNING))
        # Set channel running
        asyncio.create_task(self.from_pyboard())
        while True:
            gc.collect()
            gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
            await asyncio.sleep(1)

# Comms channel to Pyboard
channel = Channel()
asyncio.create_task(channel.start(channel.main_task))
asyncio.run(heartbeat())
