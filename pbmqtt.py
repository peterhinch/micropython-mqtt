# pbmqtt.py Implement MQTT on Pyboard using an ESP8266
# The ESP8266 runs mqtt.py on startup.
# Boards are electrically connected as per the README.
# asyncio version
# On fatal error performs hardware reset on ESP8266.

# Author: Peter Hinch.
# Copyright Peter Hinch 2017-2018 Released under the MIT license.

# SynCom throughput 118 char/s measured 8th Aug 2017 sending a publication
# while application running. ESP8266 running at 160MHz. (Chars are 7 bits).

import uasyncio as asyncio
from utime import localtime, time
import pyb
from machine import Pin, Signal
from syncom import SynCom
import asyn
from status_values import *  # Numeric status values shared with user code.

init = {
    'reset'  : Signal(Pin(Pin.board.Y4, Pin.OPEN_DRAIN), invert = True),
    'stx'    : Pin(Pin.board.Y5, Pin.OUT_PP),
    'sckout' : Pin(Pin.board.Y6, Pin.OUT_PP, value = 0),
    'srx'    : Pin(Pin.board.Y7, Pin.IN),
    'sckin'  : Pin(Pin.board.Y8, Pin.IN),
    'user_start' : None,
    'args' : (),
    'fast' : True,
    'mqtt_user' : '',
    'mqtt_pw' : '',
    'ssl' : False,
    'ssl_params' : repr({}),
    'use_default_net' : True,
    'port' : 0,
    'keepalive' : 60,
    'ping_interval' : 0,
    'clean_session' : True,
    'rtc_resync' : -1,  # Once only
    'local_time_offset' : 0,
    'debug' : False,  # ESP8266 verbose
    'verbose' : False,  # Pyboard
    'timeout' : 10,
    'max_repubs' : 4,
    'response_time' : 10,
}

def buildinit(d):
    ituple = ('init', d['ssid'], d['password'], d['broker'], d['mqtt_user'],
    d['mqtt_pw'], d['ssl_params'], int(d['use_default_net']), d['port'], int(d['ssl']),
    int(d['fast']), d['keepalive'], int(d['debug']),
    int(d['clean_session']), d['max_repubs'], d['response_time'], d['ping_interval'])
    return argformat(*ituple)

# _WIFI_DOWN is bad during initialisation
_BAD_STATUS = (BROKER_FAIL, WIFI_DOWN, UNKNOWN)
_DIRE_STATUS = (BROKER_FAIL, UNKNOWN)  # Always fatal

# Format an arbitrary list of positional args as a status_values.SEP separated string
def argformat(*a):
    return SEP.join(['{}' for x in range(len(a))]).format(*a)

def printtime():
    print('{:02d}:{:02d}:{:02d} '.format(localtime()[3], localtime()[4], localtime()[5]), end='')

def qos_check(qos):
    if not isinstance(qos, int) or not (qos == 0 or qos == 1):
        raise ValueError('Only qos 0 and 1 are supported.')

async def heartbeat():
    led = pyb.LED(1)
    while True:
        await asyncio.sleep_ms(500)
        led.toggle()

# Replace to handle status changes. In the case of fatal status values the
# ESP8266 will be rebooted on return. You may want to pause for remedial
# action before the reboot. Information statuses can be ignored with rapid
# return. Cases which may require attention:
# SPECNET return 1 to try specified network or 0 to reboot ESP. Code below
# tries specified LAN (if default LAN fails) on first run only to limit
# flash wear.
# BROKER_FAIL Pause for server fix? Return (and so reboot) after delay?
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

# Optionally synch the Pyboard's RTC to an NTP timeserver. When instantiated
# is idle bar reporting synch status. _start runs _do_rtc coro if required.
class RTCsynchroniser():
    def __init__(self, mqtt_link, interval, local_time_offset):
        self._rtc_interval = interval
        self._local_time_offset = local_time_offset
        self._rtc_last_syn = 0  # Time when last synchronised (0 == never)
        self._time_valid = False
        self._lnk = mqtt_link

    def _start(self):
        i = self._rtc_interval  # 0 == no synch. -1 == once only. > 1 = secs
        if i and (i > 0 or self._rtc_last_syn == 0):
            loop = asyncio.get_event_loop()
            loop.create_task(asyn.Cancellable(self._do_rtc)())

    @asyn.cancellable
    async def _do_rtc(self):
        lnk = self._lnk
        lnk.vbprint('Start RTC synchroniser')
        self._time_valid = not self._rtc_last_syn == 0  # Valid on restart
        while True:
            while not self._time_valid:
                lnk.channel.send(TIME)
                # Give 5s time for response
                await asyn.sleep(5)
                if not self._time_valid:
                    # WiFi may be down. Delay 1 min before retry.
                    await asyn.sleep(60)
            else:  # Valid time received or restart
                if self._rtc_interval < 0:
                    break  # One resync only: done
                tend = self._rtc_last_syn + self._rtc_interval
                twait = max(tend - time(), 5)  # Prolonged outage
                await asyn.sleep(twait)
                self._time_valid = False

    def _do_time(self, action):  # TIME received from ESP8266
        lnk = self._lnk
        try:
            t = int(action[0])
        except ValueError:  # Gibberish.
            lnk.quit('Invalid data from ESP8266')
            return
        self._time_valid = t > 0
        if self._time_valid:
            rtc = pyb.RTC()
            tm = localtime(t)
            hours = (tm[3] + self._local_time_offset) % 24
            tm = tm[0:3] + (tm[6] + 1,) + (hours,) + tm[4:6] + (0,)
            rtc.datetime(tm)
            self._rtc_last_syn = time()
            lnk.vbprint('time', localtime())
        else:
            lnk.vbprint('Bad time received.')

    # Is Pyboard RTC synchronised?
    def _rtc_syn(self):
        return self._rtc_last_syn > 0

# Pub topics and messages restricted to 7 bits, 0 and 127 disallowed.
def validate(s, item):
    s = s.encode('UTF8')
    if any(True for a in s if a == 0 or a >= 127):
        raise ValueError('Illegal character in {} in {}'.format(s, item))

# awaitable task cancellation
class Killer():
    def __await__(self):
        yield from asyn.Cancellable.cancel_all()

    __iter__ = __await__


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

    def __init__(self, d):
        self.user_start = (d['user_start'], d['args'])
        self.init_str = buildinit(d)
        # Synchroniser idle until started.
        self.rtc_synchroniser = RTCsynchroniser(self, d['rtc_resync'], d['local_time_offset'])
        self.keepalive = d['keepalive']
        self._running = False
        self.verbose = d['verbose']
        # Watchdog timeout for ESP8266 (ms).
        wdog = d['timeout'] * 1000
        # SynCom string mode
        self.channel = SynCom(False, d['sckin'], d['sckout'], d['srx'], d['stx'],
                              d['reset'], wdog, True, self.verbose)
        loop = asyncio.get_event_loop()
        loop.create_task(heartbeat())
        # Start the SynCom instance. This will run self.start(). If an error
        # occurs self.quit() is called which cancels all NamedTask instances
        # and returns to Syncom's start() method. This waits on Cancellable.cancel_all()
        # before forcing a failure on the ESP8266 and re-running self.start()
        # to perform a clean restart.
        loop.create_task(self.channel.start(self.start, Killer()))
        self.subs = {} # Callbacks indexed by topic
        self.pubs = []
        self._pub_free = True  # No publication in progress
        self.s_han = default_status_handler
        self.wifi_han = (lambda *_ : None, ())
        self._wifi_up = False
        # Only specify network on first run
        self.first_run = True


# API
    def publish(self, topic, msg, retain=False, qos=0):
        qos_check(qos)
        validate(topic, 'topic')  # Raise ValueError if invalid.
        validate(msg, 'message')
        self.pubs.append((topic, msg, 1 if retain else 0, qos))

    def pubq_len(self):
        return len(self.pubs)

    def subscribe(self, topic, qos, callback, *args):
        qos_check(qos)
        self.subs[topic] = (callback, args)
        self.channel.send(argformat(SUBSCRIBE, topic, qos))

    # Command handled directly by mqtt.py on ESP8266 e.g. MEM
    def command(self, *argsend):
        self.channel.send(argformat(*argsend))

    # Is Pyboard RTC synchronised?
    def rtc_syn(self):
        return self.rtc_synchroniser._rtc_syn()

    def status_handler(self, coro):
        self.s_han = coro

    def wifi_handler(self, cb, *args):
        self.wifi_han = (cb, args)

    def running(self):
        return self._running

    def wifi(self):
        return self._wifi_up
# API END

# Convenience method allows return self.quit() on error
    def quit(self, *args):
        if args is not ():
            self.vbprint(*args)
        self._running = False
        # Note that if this method is called from self.start return is to
        # SynCom's start method which will wait on the Killer instance to
        # cancel all Cancellable tasks

# On publication of a qos 1 message this is called with False. This prevents
# further pubs until the response is received, ensuring we wait for the PUBACK
# that corresponds to the last publication.
# This delay can be arbitrarily long if WiFi connectivity has been lost.
    def pub_free(self, val = None):
        if val is not None:
            self._pub_free = val
        return self._pub_free


    def vbprint(self, *args):
        if self.verbose:
            print(*args)

    def get_cmd(self, istr):
        ilst = istr.split(SEP)
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
        # Detect WiFi status changes. Ignore initialisation and repeats
        if last_status != -1 and iact != last_status and iact in (WIFI_UP, WIFI_DOWN):
            self._wifi_up = iact == WIFI_UP
            cb, args = self.wifi_han
            cb(self._wifi_up, *args)
        if self.verbose:
            if iact != UNKNOWN:
                if iact != last_status:  # Ignore repeats
                    printtime()
                    print('Status: ', self.status_msgs[iact])
            else:
                printtime()
                print('Unknown status: {} {}'.format(action[1], action[2]))
        return iact


# PUBLISH
    @asyn.cancellable
    async def _publish(self):
        while True:
            if len(self.pubs): 
                args = self.pubs.pop(0)
                secs = 0
                # pub free can be a long time coming if WiFi is down
                while not self._pub_free:
                    # If pubs are queued, wait 1 sec to respect ESP8266 buffers
                    await asyncio.sleep(1)
                    if self._wifi_up:
                        secs += 1
                    if secs > 60:
                        self.quit('No response from ESP8266')
                        break
                else:
                    self.channel.send(argformat(PUBLISH, *args))
                    # All pubs send PUBOK.
                    # No more pubs allowed until PUBOK received.
                    self.pub_free(False)
            else:
                await asyncio.sleep_ms(20)

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
            channel.send(argformat(WILL, self.lw_topic, self.lw_msg, self.lw_retain, self.lw_qos))
            res = await channel.await_obj()
            if res is None:  # SynCom timeout
                await self.s_han(self, ESP_FAIL)
                return self.quit('ESP8266 fail 1. Resetting.')
            command, action = self.get_cmd(res)
            if command == STATUS:
                iact = self.do_status(action, -1)
                await self.s_han(self, iact)
                if iact in _BAD_STATUS:
                    return self.quit('Bad status: {}. Resetting.'.format(iact))
            else:
                self.vbprint('Expected will OK got: ', command, action)
        channel.send(self.init_str)
        while not self._running:  # Until RUNNING status received
            res = await channel.await_obj()
            if res is None:
                await self.s_han(self, ESP_FAIL)
                return self.quit('ESP8266 fail 2. Resetting.')
            command, action = self.get_cmd(res)
            if command == STATUS:
                iact = self.do_status(action, -1)
                result = await self.s_han(self, iact)
                if iact == SPECNET:
                    if result == 1:
                        channel.send('1')  # Any string will do
                    else:
                        return self.quit()
                if iact in _BAD_STATUS:
                    return self.quit('Bad status. Resetting.')
            else:
                self.vbprint('Init got: ', command, action)

        self.vbprint('About to run user program.')
        if self.user_start is not None:
            self.user_start[0](self, *self.user_start[1])  # User start function
        loop = asyncio.get_event_loop()
        loop.create_task(asyn.Cancellable(self._publish)())
        self.rtc_synchroniser._start()  # Run coro if synchronisation is required.
        cb, args = self.wifi_han
        cb(True, *args)

# Initialisation is complete. Process messages from ESP8266.
        iact = -1                   # Invalidate last status for change detection
        while True:                 # print incoming messages, handle subscriptions
            chan_state = channel.any()
            if chan_state is None:  # SynCom Timeout
                self._running = False
            elif chan_state > 0:
                res = await channel.await_obj()
                command, action = self.get_cmd(res)
                if command == SUBSCRIPTION:
                    if action[0] in self.subs: # topic found
                        cb, args = self.subs[action[0]]
                        action += args
                        cb(*action)  # Run the callback
                elif command == STATUS:  # 1st arg of status is an integer
                    iact = self.do_status(action, iact) # Update pub q and wifi status
                    await self.s_han(self, iact)
                    if iact in _DIRE_STATUS:
                        return self.quit('Fatal status. Resetting.')
                elif command == TIME:
                    self.rtc_synchroniser._do_time(action)
                elif command == MEM:  # Wouldn't ask for this if we didn't want a printout
                    print('ESP8266 RAM free: {} allocated: {}'.format(action[0], action[1]))
                else:
                    await self.s_han(self, UNKNOWN)
                    return self.quit('Got unhandled command, resetting ESP8266:', command, action)  # ESP8266 has failed

            await asyncio.sleep_ms(20)
            if not self._running:  # self.quit() has been called.
                await self.s_han(self, NO_NET)
                return self.quit('Not running, resetting ESP8266')
