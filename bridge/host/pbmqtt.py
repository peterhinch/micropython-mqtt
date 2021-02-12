# pbmqtt.py Implement MQTT on Pyboard using an ESP8266
# The ESP8266 runs mqtt.py on startup.
# Boards are electrically connected as per the README.
# asyncio version
# On fatal error performs hardware reset on ESP8266.

# Author: Peter Hinch.
# Copyright Peter Hinch 2017-2021 Released under the MIT license.

# SynCom throughput 118 char/s measured 8th Aug 2017 sending a publication
# while application running. ESP8266 running at 160MHz. (Chars are 7 bits).


import uasyncio as asyncio
from utime import localtime, gmtime, time
from syncom import SynCom
from status_values import *  # Numeric status values shared with user code.

__version__ = (0, 1, 0)

defaults = {
    'user_start' : (lambda *_ : None, ()),
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
    'debug' : False,  # ESP8266 verbose
    'verbose' : False,  # Host
    'timeout' : 10,
    'max_repubs' : 4,
    'response_time' : 10,
    'wifi_handler' : (lambda *_ : None, ()),
    'crash_handler' : (lambda *_ : None, ()),
    'status_handler' : None,
    'timeserver' : 'pool.ntp.org',
}


def buildinit(d):
    ituple = ('init', d['ssid'], d['password'], d['broker'], d['mqtt_user'],
    d['mqtt_pw'], d['ssl_params'], int(d['use_default_net']), d['port'], int(d['ssl']),
    int(d['fast']), d['keepalive'], int(d['debug']),
    int(d['clean_session']), d['max_repubs'], d['response_time'], d['ping_interval'],
    d['timeserver'])
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

async def heartbeat(led):
    while True:
        await asyncio.sleep_ms(500)
        led(not led())

# Replace to handle status changes. In the case of fatal status values the
# ESP8266 will be rebooted on return. You may want to pause for remedial
# action before the reboot. Information statuses can be ignored with rapid
# return. Cases which may require attention:
# SPECNET return 1 to try specified network or 0 to reboot ESP. Code below
# tries specified LAN (if default LAN fails) on first run only to limit
# flash wear.
# BROKER_FAIL Pause for server fix? Return (and so reboot) after delay?

async def default_status_handler(mqtt_link, status):
    await asyncio.sleep_ms(0)
    if status == SPECNET:
        if mqtt_link.first_run:
            mqtt_link.first_run = False
            return 1  # By default try specified network on 1st run only
        asyncio.sleep(30)  # Pause before reboot.
        return 0  # Return values are for user handlers: see pb_status.py

# Pub topics and messages restricted to 7 bits, 0 and 127 disallowed.
def validate(s, item):
    s = s.encode('UTF8')
    if any(True for a in s if a == 0 or a >= 127):
        raise ValueError('Illegal character in {} in {}'.format(s, item))


class MQTTlink:
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
                'publish OK', 'running', 'unknown', 'Will registered', 'Fail to connect to broker',
                'WiFi up', 'WiFi down')

    def __init__(self, *args, **kwargs):
        d = defaults  # d is the config dict: initially populate with default values
        for arg in args:
            d.update(arg)  # Hardware and network configs
        d.update(kwargs)
        # d is now populated.
        self.user_start = d['user_start']
        shan = d['status_handler']
        self.s_han = (default_status_handler, ()) if shan is None else shan  # coro
        self.crash_han = d['crash_handler']
        self.wifi_han = d['wifi_handler']
        self.init_str = buildinit(d)
        self.keepalive = d['keepalive']
        self._evtrun = asyncio.Event()
        self.verbose = d['verbose']
        # Watchdog timeout for ESP8266 (ms).
        wdog = d['timeout'] * 1000
        # SynCom string mode
        self.channel = SynCom(False, d['sckin'], d['sckout'], d['srx'], d['stx'],
                              d['reset'], wdog, True, self.verbose)
        if 'led' in d:
            asyncio.create_task(heartbeat(d['led']))
        # Start the SynCom instance. This will run self.start(). If an error
        # occurs self.quit() is called which returns to Syncom's start() method.
        # This waits on ._die before forcing a failure on the ESP8266 and re-running
        # self.start() to perform a clean restart.
        asyncio.create_task(self.channel.start(self.start, self._die))
        self.subs = {}  # (callback, qos, args) indexed by topic
        self.publock = asyncio.Lock()
        self.puback = asyncio.Event()
        self.evttim = asyncio.Event()
        self.evtwifi = asyncio.Event()
        # Only specify network on first run
        self.first_run = True
        self._time = 0  # NTP time. Invalid.
        # ESP8266 returns seconds from 2000 because I believed the docs.
        # Maintainers change the epoch on a whim.
        # Calculate ofsets in CPython using datetime.date:
        # (date(2000, 1, 1) - date(1970, 1, 1)).days * 24*60*60
        epoch = {2000 : 0, 1970 : 946684800}  # Offset to add.
        self._epoch_fix = epoch[gmtime(0)[0]]  # Find offset on current platform

# API
    async def publish(self, topic, msg, retain=False, qos=0):
        qos_check(qos)
        validate(topic, 'topic')  # Raise ValueError if invalid.
        validate(msg, 'message')
        await self.ready()
        async with self.publock:
            self.channel.send(argformat(PUBLISH, topic, msg, int(retain), qos))
            # Wait for ESP8266 to complete. Quick if qos==0. May be very slow
            # in an outage
            await self.puback.wait()

    async def subscribe(self, topic, qos, callback, *args):
        qos_check(qos)
        # Save subscription to resubscribe after outage
        self.subs[topic] = (callback, qos, args)
        # Subscribe
        await self.ready()
        self.channel.send(argformat(SUBSCRIBE, topic, qos))

    # Command handled directly by mqtt.py on ESP8266 e.g. MEM
    async def command(self, *argsend):
        await self.ready()
        self.channel.send(argformat(*argsend))

    def running(self):
        return self._evtrun.is_set()

    async def ready(self):
        await self._evtrun.wait()
        await self.evtwifi.wait()

    def wifi(self):
        return self.evtwifi.is_set()

    # Attempt to retrieve NTP time in secs since 2000 or device epoch
    async def get_time(self, pause=120, y2k=False):
        delta = 0 if y2k else self._epoch_fix
        self.evttim.clear()  # Defensive
        self._time = 0  # Invalidate
        while True:
            await self.ready()
            self.channel.send(TIME)
            try:
                await asyncio.wait_for(self.evttim.wait(), pause // 2)
            except asyncio.TimeoutError:
                pass
            if self._time:
                return self._time + delta  # Fix epoch
            await asyncio.sleep(pause)
        
# API END
    def _do_time(self, action):  # TIME received from ESP8266
        try:
            self._time = int(action[0])
        except ValueError:  # Gibberish.
            self._time = 0  # May be 0 if ESP has signalled failure
        self.evttim.set()
        self.evttim.clear()

    async def _die(self):  # ESP has crashed. Run user callback if provided.
        cb, args = self.crash_han
        cb(self, *args)
        await asyncio.sleep_ms(0)

# Convenience method allows this error code:
# return self.quit(message)
# This method is called from self.start. Note that return is to SynCom's
# .start method which will launch ._die
    def quit(self, *args):
        if args is not ():
            self.verbose and print(*args)
        self._evtrun.clear()

    def get_cmd(self, istr):
        ilst = istr.split(SEP)
        return ilst[0], ilst[1:]

    def do_status(self, action, last_status):
        try:
            iact = int(action[0])
        except ValueError:  # Gibberish from ESP8266: caller reboots
            return UNKNOWN
        if iact == PUBOK:
            # Occurs after all publications. If qos==0 immediately, otherwise
            # when PUBACK received from broker. May take a long time in outage.
            # If a crash occurs, puback is cleared by start()
            self.puback.set()
            self.puback.clear()
        elif iact == RUNNING:
            self._evtrun.set()
        if iact == WIFI_UP:
            self.evtwifi.set()
        elif iact == WIFI_DOWN:
            self.evtwifi.clear()
        # Detect WiFi status changes. Ignore initialisation and repeats
        if last_status != -1 and iact != last_status and iact in (WIFI_UP, WIFI_DOWN):
            cb, args = self.wifi_han
            cb(self.evtwifi.is_set(), self, *args)
        if self.verbose:
            if iact != UNKNOWN:
                if iact != last_status:  # Ignore repeats
                    printtime()
                    print('Status: ', self.status_msgs[iact])
            else:
                printtime()
                print('Unknown status: {} {}'.format(action[1], action[2]))
        return iact

# start() is run each time the channel acquires sync i.e. on startup and also
# after an ESP8266 crash and reset.
# Behaviour after fatal error with ESP8266:
# It clears ._evtrun to cause local tasks to terminate, then returns.
# A return causes the local channel instance to launch .die then issues
# a hardware reset to the ESP8266 (See SynCom.start() and .run() methods).
# After acquiring sync, start() gets rescheduled.
    async def start(self, channel):
        self.verbose and print('Starting...')
        self.puback.set()  # If a crash occurred while a pub was pending
        self.puback.clear()  # let it terminate and release the lock
        self.evttim.set()  # Likewise for get_time: let it return fail status.
        self.evttim.clear()
        await asyncio.sleep_ms(0)
        self._evtrun.clear()  # Set by .do_status
        s_task, s_args = self.s_han
        if self.lw_topic is not None:
            channel.send(argformat(WILL, self.lw_topic, self.lw_msg, self.lw_retain, self.lw_qos))
            res = await channel.await_obj()
            if res is None:  # SynCom timeout
                await s_task(self, ESP_FAIL, *s_args)
                return self.quit('ESP8266 fail 1. Resetting.')
            command, action = self.get_cmd(res)
            if command == STATUS:
                iact = self.do_status(action, -1)
                await s_task(self, iact, *s_args)
                if iact in _BAD_STATUS:
                    return self.quit('Bad status: {}. Resetting.'.format(iact))
            else:
                self.verbose and print('Expected will OK got: ', command, action)
        channel.send(self.init_str)
        while not self._evtrun.is_set():  # Until RUNNING status received
            res = await channel.await_obj()
            if res is None:
                await s_task(self, ESP_FAIL, *s_args)
                return self.quit('ESP8266 fail 2. Resetting.')
            command, action = self.get_cmd(res)
            if command == STATUS:
                iact = self.do_status(action, -1)
                result = await s_task(self, iact, *s_args)
                if iact == SPECNET:
                    if result == 1:
                        channel.send('1')  # Any string will do
                    else:
                        return self.quit()
                if iact in _BAD_STATUS:
                    return self.quit('Bad status. Resetting.')
            else:
                self.verbose and print('Init got: ', command, action)
        # On power up this will do nothing because user awaits .ready
        # before subscribing, so self.subs will be empty.
        for topic in self.subs:
            qos = self.subs[topic][1]
            self.channel.send(argformat(SUBSCRIBE, topic, qos))

        self.verbose and print('About to run user program.')
        if self.user_start[0] is not None:
            self.user_start[0](self, *self.user_start[1])  # User start function
        cb, args = self.wifi_han
        cb(True, self, *args)

# Initialisation is complete. Process messages from ESP8266.
        iact = -1  # Invalidate last status for change detection
        while True:  # print incoming messages, handle subscriptions
            chan_state = channel.any()
            if chan_state is None:  # SynCom Timeout
                self._evtrun.clear()
            elif chan_state > 0:
                res = await channel.await_obj()
                command, action = self.get_cmd(res)
                if command == SUBSCRIPTION:
                    if action[0] in self.subs: # topic found
                        cb, qos, args = self.subs[action[0]]
                        action += args
                        # Callback gets topic, message, retained, plus any user args
                        cb(*action)  # Run the callback
                elif command == STATUS:  # 1st arg of status is an integer
                    iact = self.do_status(action, iact) # Update pub q and wifi status
                    await s_task(self, iact, *s_args)
                    if iact in _DIRE_STATUS:
                        return self.quit('Fatal status. Resetting.')
                elif command == TIME:
                    self._do_time(action)
                elif command == MEM:  # Wouldn't ask for this if we didn't want a printout
                    print('ESP8266 RAM free: {} allocated: {}'.format(action[0], action[1]))
                else:
                    await s_task(self, UNKNOWN, *s_args)
                    return self.quit('Got unhandled command, resetting ESP8266:', command, action)  # ESP8266 has failed

            await asyncio.sleep_ms(20)
            if not self._evtrun.is_set():  # self.quit() has been called.
                await s_task(self, NO_NET, *s_args)
                return self.quit('Not running, resetting ESP8266')
