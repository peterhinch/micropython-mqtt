# pbmqtt.py Implement MQTT on Pyboard using an ESP8266
# The ESP8266 runs mqtt.py on startup.
# Boards are electrically connected as per the README.
# asyncio version
# On fatal error performs hardware reset on ESP8266.

# Author: Peter Hinch.
# Copyright Peter Hinch 2017 Released under the MIT license.

# Latency ~500ms tested using echo.py running on PC with broker running on Pi
# (half time for round-trip)

import uasyncio as asyncio
from utime import localtime, time
import pyb
from syncom import SynCom
from aswitch import Delay_ms
from asyn import ExitGate
from status_values import *  # Numeric status values shared with user code.

# _WIFI_DOWN is bad during initialisation
_BAD_STATUS = (BROKER_FAIL, WIFI_DOWN, UNKNOWN)
_DIRE_STATUS = (BROKER_FAIL, UNKNOWN)  # Always fatal

# Format an arbitrary list of positional args as a comma separated string
def argformat(*a):
    return ','.join(['{}' for x in range(len(a))]).format(*a)

def printtime():
    print('{:02d}:{:02d}:{:02d} '.format(localtime()[3], localtime()[4], localtime()[5]), end='')

async def heartbeat():
    led = pyb.LED(1)
    while True:
        await asyncio.sleep_ms(500)
        led.toggle()

# Subclass to handle status changes. In the case of fatal status values the
# ESP8266 will be rebooted on return. You may want to pause for remedial
# action before the reboot. Information statuses can be ignored with rapid
# return. Cases which may require attention:
# SPECNET return 1 to try specified network or 0 to reboot ESP. Code below
# tries specified LAN (if default LAN fails) on first run only to limit
# flash wear.
# BROKER_FAIL Pause for server fix? Return (and so reboot) after delay?
# NO_NET WiFi has timed out.
# Pauses must be implemented with the following to ensure task quits on fail
#     if not await self.exit_gate.sleep(delay_in_secs):
#         return

async def default_status_handler(mqtt_link, status):
    await asyncio.sleep_ms(0)
    if status == SPECNET:
        if mqtt_link.first_run:
            mqtt_link.first_run = False
            return 1  # By default try specified network on 1st run only
        asyncio.sleep(30)  # Pause before reboot.
        return 0

class MQTTlink(object):
    lw_topic = None
    lw_msg = None
    lw_retain = False
    lw_qos = 0
    @classmethod
    def will(cls, topic, msg, retain=False, qos=0):
        cls.lw_topic = topic
        cls.lw_msg = msg
        cls.lw_retain = retain
        cls.lw_qos = qos
    status_msgs = ('connected to broker', 'awaiting broker',
                'awaiting default network', 'awaiting specified network',
                'publish OK', 'running', 'unk', 'Will registered', 'Fail to connect to broker',
                'WiFi up', 'WiFi down')

    def __init__(self, reset, sckin, sckout, srx, stx, init, user_start=None,
                 args=(), local_time_offset=0, verbose=True, timeout=10):
        self.user_start = (user_start, args)
        self.local_time_offset = local_time_offset
        self.init_str = argformat(*init)
        self.keepalive = init[12]
        self._rtc_syn = False  # RTC persists over ESP8266 reboots
        self._running = False
        self.verbose = verbose
        wdog = timeout * 1000  # Blocking timeout for ESP8266
        # SynCom string mode
        self.channel = SynCom(False, sckin, sckout, srx, stx, reset, wdog, True, verbose)
        loop = asyncio.get_event_loop()
        loop.create_task(heartbeat())
        self.exit_gate = ExitGate()
        loop.create_task(self.channel.start(self.start, self.exit_gate))
        self.subs = {} # Callbacks indexed by topic
        self.pubs = []
        self._pub_free = True  # No publication in progress
        self.pub_delay = Delay_ms(self.quit)  # Wait for qos 1 response
        self.s_han = default_status_handler
        # Only specify network on first run
        self.first_run = True


# API
    def publish(self, topic, msg, retain=False, qos=0):
        self.pubs.append((topic, msg, retain, qos))

    def pubq_len(self):
        return len(self.pubs)

    def subscribe(self, topic, callback, qos=0):
        self.subs[topic] = callback
        self.channel.send(argformat('subscribe', topic, qos))

    # Command handled directly by mqtt.py on ESP8266 e.g. 'mem'
    def command(self, *argsend):
        self.channel.send(argformat(*argsend))

    # Is Pyboard RTC synchronised?
    def rtc_syn(self):
        return self._rtc_syn

    def status_handler(self, coro):
        self.s_han = coro

    def running(self):
        return self._running
# API END

# Convenience method allows return self.quit() on error
    def quit(self, *args):
        if args is not ():
            self.vbprint(*args)
        self._running = False

# On publication of a qos 1 message this is called with False. This prevents
# further pubs until the response is received, ensuring we wait for the PUBACK
# that corresponds to the last publication.
# So publication starts the pub response timer, which on timeout sets _running
# False
# A puback message calls pub_free(True) which stops the timer.
# IOW if the PUBACK is not received within the keepalive period assume we're
# broken and restart.
    def pub_free(self, val = None):
        if val is not None:
            self._pub_free = val
            if val:
                self.pub_delay.stop()
            else:
                self.pub_delay.trigger(self.keepalive * 1000)
        return self._pub_free


    def vbprint(self, *args):
        if self.verbose:
            print(*args)

    def get_cmd(self, istr):
        ilst = istr.split(',')
        return ilst[0], ilst[1:]

    def do_status(self, action, last_status):
        try:
            iact = int(action[0])
        except ValueError:  # Gibberish from ESP8266: caller reboots
            return UNKNOWN
        if iact == PUBOK:
            self.pub_free(True)  # Unlock so we can do another pub.
        elif iact == RUNNING:
            self._running = True
        if self.verbose:
            if iact != UNKNOWN:
                if iact != last_status:  # Ignore repeats
                    printtime()
                    print('Status: ', self.status_msgs[iact])
            else:
                printtime()
                print('Unknown status: {} {}'.format(action[1], action[2]))
        return iact

    def do_time(self, action):
        try:
            t = int(action[0])
        except ValueError:
            self._running = False
            return
        rtc = pyb.RTC()
        tm = localtime(t)
        hours = (tm[3] + self.local_time_offset) % 24
        tm = tm[0:3] + (tm[6] + 1,) + (hours,) + tm[4:6] + (0,)
        rtc.datetime(tm)
        self._rtc_syn = True
        self.vbprint('time', localtime())

    async def _publish(self):
        egate = self.exit_gate
        async with egate:
            while not egate.ending():  # Until parent task has died
                await asyncio.sleep_ms(100)
                if len(self.pubs) and self._pub_free:
                    args = self.pubs.pop(0)
                    self.channel.send(argformat('publish', *args))
                    # In this version all pubs send PUBOK
                    # Set _pub_free False and start timer. If no response
                    # received in the keepalive period _running is set False and we
                    # reboot the ESP8266
                    self.pub_free(False)

# start() is run each time the channel acquires sync i.e. on startup and also
# after an ESP8266 crash and reset.
# Behaviour after fatal error with ESP8266:
# It sets _running False to cause local tasks to terminate, then returns.
# A return causes the local channel instance to wait on the exit_gate to cause
# tasks in this program terminate, then issues a hardware reset to the ESP8266.
# (See SynCom.start() method). After acquiring sync, start() gets rescheduled.
    async def start(self, channel):
        self.vbprint('Starting...')
        self.subs = {} # Callbacks indexed by topic
        self._pub_free = True  # No publication in progress
        self._running = False
        if self.lw_topic is not None:
            channel.send(argformat('will', self.lw_topic, self.lw_msg, self.lw_retain, self.lw_qos))
            res = await channel.await_obj()
            if res is None:  # SynCom timeout
                await self.s_han(self, ESP_FAIL)
                return self.quit('ESP8266 fail 1. Resetting.')
            command, action = self.get_cmd(res)
            if command == 'status':
                iact = self.do_status(action, -1)
                await self.s_han(self, iact)
                if iact in _BAD_STATUS:
                    return self.quit('Bad status. Resetting.')
            else:
                self.vbprint('Expected will OK got: ', command, action)
        channel.send(self.init_str)
        while not self._running:  # Until RUNNING status received
            res = await channel.await_obj()
            if res is None:
                await self.s_han(self, ESP_FAIL)
                return self.quit('ESP8266 fail 2. Resetting.')
            command, action = self.get_cmd(res)
            if command == 'status':
                iact = self.do_status(action, -1)
                result = await self.s_han(self, iact)
                if iact == SPECNET:
                    if result == 1:
                        channel.send('1')  # Any string will do
                    else:
                        return self.quit()
                if iact in _BAD_STATUS:
                    return self.quit('Bad status. Resetting.')
            elif command == 'time':
                self.do_time(action)
            else:
                self.vbprint('Init got: ', command, action)

        self.vbprint('About to run user program.')
        if self.user_start is not None:
            self.user_start[0](self, *self.user_start[1])  # User start function

        loop = asyncio.get_event_loop()
        loop.create_task(self._publish())
        iact = -1                   # Invalidate last status for change detection
        while True:                 # print incoming messages, handle subscriptions
            res = await channel.await_obj()
            if res is None:         # SynCom timeout
                await self.s_han(self, ESP_FAIL)
                return self.quit('ESP8266 fail 3. Resetting.')  # ESP8266 fail

            command, action = self.get_cmd(res)
            if command == 'subs':   # It's a subscription
                if action[0] in self.subs: # topic found
                    self.subs[action[0]](*action)  # Run the callback
            elif command == 'status':  # 1st arg of status is an integer
                iact = self.do_status(action, iact) # Update pub q and wifi status
                await self.s_han(self, iact)
                if iact in _DIRE_STATUS:  # Tolerate brief WiFi outages: let channel timeout
                    return self.quit('Fatal status. Resetting.')
            elif command == 'time':
                self.do_time(action)
            elif command == 'mem':  # Wouldn't ask for this if we didn't want a printout
                print('ESP8266 RAM free: {} allocated: {}'.format(action[0], action[1]))
            else:
                await self.s_han(self, UNKNOWN)
                return self.quit('Got unhandled command, resetting ESP8266:', command, action)  # ESP8266 has failed

            if not self._running:  # puback not received?
                await self.s_han(self, NO_NET)
                return self.quit('Not running, resetting ESP8266')

