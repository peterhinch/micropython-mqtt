# mqtt_as.py Asynchronous version of umqtt.robust
# (C) Copyright Peter Hinch 2017-2021.
# Released under the MIT licence.

# Pyboard D support added
# Various improvements contributed by Kevin Köck.

import gc
import sys
import ustruct as struct

# imported here to optimize RAM usage
from .interfaces import BaseInterface

gc.collect()
from ubinascii import hexlify
import uasyncio as asyncio

gc.collect()
from utime import ticks_ms, ticks_diff

gc.collect()
from micropython import const

if sys.platform != 'linux':
    from machine import unique_id

VERSION = (0, 7, 0)

# Default short delay for good SynCom throughput (avoid sleep(0) with SynCom).
_DEFAULT_MS = const(20)
_SOCKET_POLL_DELAY = const(5)  # 100ms added greatly to publish latency


# Default "do little" coro for optional user replacement
async def eliza(*_):  # e.g. via set_wifi_handler(coro): see test program
    await asyncio.sleep_ms(_DEFAULT_MS)


config = {
    'client_id':     hexlify(unique_id()) if sys.platform != 'linux' else 'linux',
    'server':        None,
    'port':          0,
    'user':          '',
    'password':      '',
    'keepalive':     60,
    'ping_interval': 0,
    'ssl':           False,
    'ssl_params':    {},
    'response_time': 10,
    'clean_init':    True,
    'clean':         True,
    'max_repubs':    4,
    'will':          None,
    'subs_cb':       lambda *_: None,
    'wifi_coro':     None,
    'connect_coro':  eliza,
    'ssid':          None,
    'wifi_pw':       None,
    'interface':     None,
}


class MQTTException(Exception):
    pass


def pid_gen():
    pid = 0
    while True:
        pid = pid + 1 if pid < 65535 else 1
        yield pid


def qos_check(qos):
    if not (qos == 0 or qos == 1):
        raise ValueError('Only qos 0 and 1 are supported.')


# MQTT_base class. Handles MQTT protocol on the basis of a good connection.
# Exceptions from connectivity failures are handled by MQTTClient subclass.
class MQTT_base:
    REPUB_COUNT = 0  # TEST
    DEBUG = False

    def __init__(self, config):
        # MQTT config
        self._client_id = config['client_id']
        self._user = config['user']
        self._pswd = config['password']
        self._keepalive = config['keepalive']
        if self._keepalive >= 65536:
            raise ValueError('invalid keepalive time')
        self._response_time = config['response_time'] * 1000  # Repub if no PUBACK received (ms).
        self._max_repubs = config['max_repubs']
        self._clean_init = config['clean_init']  # clean_session state on first connection
        self._clean = config['clean']  # clean_session state on reconnect
        will = config['will']
        if will is None:
            self._lw_topic = False
        else:
            self._set_last_will(*will)
        # Interface config
        if 'interface' not in config or config['interface'] is None:
            if sys.platform == 'linux':
                from .interfaces.linux import Linux
                self._interface = Linux()
            else:
                # assume WLAN interface, backwards compatibility
                from .interfaces.wlan import WLAN
                self._interface = WLAN(config['ssid'], config['wifi_pw'])
        else:
            self._interface: BaseInterface = config['interface']
        self._ssl = config['ssl']
        self._ssl_params = config['ssl_params']
        # Callbacks and coros
        self._cb = config['subs_cb']
        if config['wifi_coro']:
            self._interface.subscribe(config['wifi_coro'])
        self._connect_handler = config['connect_coro']
        # Network
        self.port = config['port']
        if self.port == 0:
            self.port = 8883 if self._ssl else 1883
        self.server = config['server']
        if self.server is None:
            raise ValueError('no server specified.')
        self._sock = None

        self.newpid = pid_gen()
        self.rcv_pids = set()  # PUBACK and SUBACK pids awaiting ACK response
        self.last_rx = ticks_ms()  # Time of last communication from broker
        self.lock = asyncio.Lock()

    def _set_last_will(self, topic, msg, retain=False, qos=0):
        qos_check(qos)
        if not topic:
            raise ValueError('Empty topic.')
        self._lw_topic = topic
        self._lw_msg = msg
        self._lw_qos = qos
        self._lw_retain = retain

    def dprint(self, *args):
        if self.DEBUG:
            print(*args)

    def _timeout(self, t):
        return ticks_diff(ticks_ms(), t) > self._response_time

    async def _as_read(self, n, sock=None):  # OSError caught by superclass
        if sock is None:
            sock = self._sock
        data = b''
        t = ticks_ms()
        while len(data) < n:
            if self._timeout(t) or not self.isconnected():
                raise OSError(-1)
            try:
                msg = sock.read(n - len(data))
            except OSError as e:  # ESP32 issues weird 119 errors here
                msg = None
                if e.args[0] not in self._interface.BUSY_ERRORS:
                    raise
            if msg == b'':  # Connection closed by host
                raise OSError(-1)
            if msg is not None:  # data received
                data = b''.join((data, msg))
                t = ticks_ms()
                self.last_rx = ticks_ms()
            await asyncio.sleep_ms(_SOCKET_POLL_DELAY)
        return data

    async def _as_write(self, bytes_wr, length=0, sock=None):
        if sock is None:
            sock = self._sock
        if length:
            bytes_wr = bytes_wr[:length]
        t = ticks_ms()
        while bytes_wr:
            if self._timeout(t) or not self.isconnected():
                raise OSError(-1)
            try:
                n = sock.write(bytes_wr)
            except OSError as e:  # ESP32 issues weird 119 errors here
                n = 0
                if e.args[0] not in self._interface.BUSY_ERRORS:
                    raise
            if n:
                t = ticks_ms()
                bytes_wr = bytes_wr[n:]
            await asyncio.sleep_ms(_SOCKET_POLL_DELAY)

    async def _send_str(self, s):
        await self._as_write(struct.pack("!H", len(s)))
        await self._as_write(s)

    async def _recv_len(self):
        n = 0
        sh = 0
        while 1:
            res = await self._as_read(1)
            b = res[0]
            n |= (b & 0x7f) << sh
            if not b & 0x80:
                return n
            sh += 7

    async def _connect(self, clean):
        self._sock = self._interface.socket.socket()
        self._sock.setblocking(False)
        try:
            self._sock.connect(self._addr)
        except OSError as e:
            if e.args[0] not in self._interface.BUSY_ERRORS:
                raise
        await asyncio.sleep_ms(_DEFAULT_MS)
        self.dprint('Connecting to broker.')
        if self._ssl:
            import ussl
            self._sock = ussl.wrap_socket(self._sock, **self._ssl_params)
        premsg = bytearray(b"\x10\0\0\0\0\0")
        msg = bytearray(b"\x04MQTT\x04\0\0\0")  # Protocol 3.1.1

        sz = 10 + 2 + len(self._client_id)
        msg[6] = clean << 1
        if self._user:
            sz += 2 + len(self._user) + 2 + len(self._pswd)
            msg[6] |= 0xC0
        if self._keepalive:
            msg[7] |= self._keepalive >> 8
            msg[8] |= self._keepalive & 0x00FF
        if self._lw_topic:
            sz += 2 + len(self._lw_topic) + 2 + len(self._lw_msg)
            msg[6] |= 0x4 | (self._lw_qos & 0x1) << 3 | (self._lw_qos & 0x2) << 3
            msg[6] |= self._lw_retain << 5

        i = 1
        while sz > 0x7f:
            premsg[i] = (sz & 0x7f) | 0x80
            sz >>= 7
            i += 1
        premsg[i] = sz
        await self._as_write(premsg, i + 2)
        await self._as_write(msg)
        await self._send_str(self._client_id)
        if self._lw_topic:
            await self._send_str(self._lw_topic)
            await self._send_str(self._lw_msg)
        if self._user:
            await self._send_str(self._user)
            await self._send_str(self._pswd)
        # Await CONNACK
        # read causes ECONNABORTED if broker is out; triggers a reconnect.
        resp = await self._as_read(4)
        self.dprint('Connected to broker.')  # Got CONNACK
        if resp[3] != 0 or resp[0] != 0x20 or resp[1] != 0x02:
            raise OSError(-1)  # Bad CONNACK e.g. authentication fail.

    async def _ping(self):
        async with self.lock:
            await self._as_write(b"\xc0\0")

    # Check internet connectivity by sending DNS lookup to Google's 8.8.8.8
    async def wan_ok(self,
                     packet=b'$\x1a\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x03www\x06google\x03com\x00\x00\x01\x00\x01'):
        if not self.isconnected():  # WiFi is down
            return False
        length = 32  # DNS query and response packet size
        s = self._interface.socket.socket(self._interface.socket.AF_INET,
                                          self._interface.socket.SOCK_DGRAM)
        s.setblocking(False)
        s.connect(('8.8.8.8', 53))
        await asyncio.sleep(1)
        try:
            await self._as_write(packet, sock=s)
            await asyncio.sleep(2)
            res = await self._as_read(length, s)
            if len(res) == length:
                return True  # DNS response size OK
        except OSError:  # Timeout on read: no connectivity.
            return False
        finally:
            s.close()
        return False

    async def broker_up(self):  # Test broker connectivity
        if not self.isconnected():
            return False
        tlast = self.last_rx
        if ticks_diff(ticks_ms(), tlast) < 1000:
            return True
        try:
            await self._ping()
        except OSError:
            return False
        t = ticks_ms()
        while not self._timeout(t):
            await asyncio.sleep_ms(100)
            if ticks_diff(self.last_rx, tlast) > 0:  # Response received
                return True
        return False

    async def disconnect(self):
        try:
            async with self.lock:
                self._sock.write(b"\xe0\0")
        except OSError:
            pass
        self._has_connected = False
        self.close()

    def close(self):
        if self._sock is not None:
            self._sock.close()

    async def _await_pid(self, pid):
        t = ticks_ms()
        while pid in self.rcv_pids:  # local copy
            if self._timeout(t) or not self.isconnected():
                break  # Must repub or bail out
            await asyncio.sleep_ms(100)
        else:
            return True  # PID received. All done.
        return False

    # qos == 1: coro blocks until wait_msg gets correct PID.
    # If WiFi fails completely subclass re-publishes with new PID.
    async def publish(self, topic, msg, retain, qos):
        pid = next(self.newpid)
        if qos:
            self.rcv_pids.add(pid)
        async with self.lock:
            await self._publish(topic, msg, retain, qos, 0, pid)
        if qos == 0:
            return

        count = 0
        while 1:  # Await PUBACK, republish on timeout
            if await self._await_pid(pid):
                return
            # No match
            if count >= self._max_repubs or not self.isconnected():
                raise OSError(-1)  # Subclass to re-publish with new PID
            async with self.lock:
                await self._publish(topic, msg, retain, qos, dup=1, pid=pid)  # Add pid
            count += 1
            self.REPUB_COUNT += 1

    async def _publish(self, topic, msg, retain, qos, dup, pid):
        pkt = bytearray(b"\x30\0\0\0")
        pkt[0] |= qos << 1 | retain | dup << 3
        sz = 2 + len(topic) + len(msg)
        if qos > 0:
            sz += 2
        if sz >= 2097152:
            raise MQTTException('Strings too long.')
        i = 1
        while sz > 0x7f:
            pkt[i] = (sz & 0x7f) | 0x80
            sz >>= 7
            i += 1
        pkt[i] = sz
        await self._as_write(pkt, i + 1)
        await self._send_str(topic)
        if qos > 0:
            struct.pack_into("!H", pkt, 0, pid)
            await self._as_write(pkt, 2)
        await self._as_write(msg)

    # Can raise OSError if WiFi fails. Subclass traps
    async def subscribe(self, topic, qos):
        pkt = bytearray(b"\x82\0\0\0")
        pid = next(self.newpid)
        self.rcv_pids.add(pid)
        struct.pack_into("!BH", pkt, 1, 2 + 2 + len(topic) + 1, pid)
        async with self.lock:
            await self._as_write(pkt)
            await self._send_str(topic)
            await self._as_write(qos.to_bytes(1, "little"))

        if not await self._await_pid(pid):
            raise OSError(-1)

    # Wait for a single incoming MQTT message and process it.
    # Subscribed messages are delivered to a callback previously
    # set by .setup() method. Other (internal) MQTT
    # messages processed internally.
    # Immediate return if no data available. Called from ._handle_msg().
    async def wait_msg(self):
        res = self._sock.read(1)  # Throws OSError on WiFi fail
        if res is None:
            return
        if res == b'':
            raise OSError(-1)

        if res == b"\xd0":  # PINGRESP
            await self._as_read(1)  # Update .last_rx time
            return
        op = res[0]

        if op == 0x40:  # PUBACK: save pid
            sz = await self._as_read(1)
            if sz != b"\x02":
                raise OSError(-1)
            rcv_pid = await self._as_read(2)
            pid = rcv_pid[0] << 8 | rcv_pid[1]
            if pid in self.rcv_pids:
                self.rcv_pids.discard(pid)
            else:
                raise OSError(-1)

        if op == 0x90:  # SUBACK
            resp = await self._as_read(4)
            if resp[3] == 0x80:
                raise OSError(-1)
            pid = resp[2] | (resp[1] << 8)
            if pid in self.rcv_pids:
                self.rcv_pids.discard(pid)
            else:
                raise OSError(-1)

        if op & 0xf0 != 0x30:
            return
        sz = await self._recv_len()
        topic_len = await self._as_read(2)
        topic_len = (topic_len[0] << 8) | topic_len[1]
        topic = await self._as_read(topic_len)
        sz -= topic_len + 2
        if op & 6:
            pid = await self._as_read(2)
            pid = pid[0] << 8 | pid[1]
            sz -= 2
        msg = await self._as_read(sz)
        retained = op & 0x01
        self._cb(topic, msg, bool(retained))
        if op & 6 == 2:  # qos 1
            pkt = bytearray(b"\x40\x02\0\0")  # Send PUBACK
            struct.pack_into("!H", pkt, 2, pid)
            await self._as_write(pkt)
        elif op & 6 == 4:  # qos 2 not supported
            raise OSError(-1)


# MQTTClient class. Handles issues relating to connectivity.

class MQTTClient(MQTT_base):
    def __init__(self, config):
        super().__init__(config)
        self._isconnected = False  # Current connection state
        keepalive = 1000 * self._keepalive  # ms
        self._ping_interval = keepalive // 4 if keepalive else 20000
        p_i = config['ping_interval'] * 1000  # Can specify shorter e.g. for subscribe-only
        if p_i and p_i < self._ping_interval:
            self._ping_interval = p_i
        self._in_connect = False
        self._has_connected = False  # Define 'Clean Session' value to use.

    async def connect(self):
        if not self._has_connected:
            if not await self._interface.connect():  # On 1st call, caller handles error
                raise OSError
            # Note this blocks if DNS lookup occurs. Do it once to prevent
            # blocking during later internet outage:
            self._addr = self._interface.socket.getaddrinfo(self.server, self.port)[0][-1]
        self._in_connect = True  # Disable low level ._isconnected check
        clean = self._clean if self._has_connected else self._clean_init
        try:
            await self._connect(clean)
        except Exception:
            self.close()
            raise
        self.rcv_pids.clear()
        # If we get here without error broker/LAN must be up.
        self._isconnected = True
        self._in_connect = False  # Low level code can now check connectivity.
        if not self._has_connected:
            self._has_connected = True  # Use normal clean flag on reconnect.
            asyncio.create_task(
                self._keep_connected())  # Runs forever unless user issues .disconnect()

        asyncio.create_task(self._handle_msg())  # Tasks quit on connection fail.
        asyncio.create_task(self._keep_alive())
        if self.DEBUG:
            asyncio.create_task(self._memory())
        asyncio.create_task(self._connect_handler(self))  # User handler.

    # Launched by .connect(). Runs until connectivity fails. Checks for and
    # handles incoming messages.
    async def _handle_msg(self):
        try:
            while self.isconnected():
                async with self.lock:
                    await self.wait_msg()  # Immediate return if no message
                await asyncio.sleep_ms(_DEFAULT_MS)  # Let other tasks get lock

        except OSError:
            pass
        self._reconnect()  # Broker or WiFi fail.

    # Keep broker alive MQTT spec 3.1.2.10 Keep Alive.
    # Runs until ping failure or no response in keepalive period.
    async def _keep_alive(self):
        while self.isconnected():
            pings_due = ticks_diff(ticks_ms(), self.last_rx) // self._ping_interval
            if pings_due >= 4:
                self.dprint('Reconnect: broker fail.')
                break
            await asyncio.sleep_ms(self._ping_interval)
            try:
                await self._ping()
            except OSError:
                break
        self._reconnect()  # Broker or WiFi fail.

    # DEBUG: show RAM messages.
    async def _memory(self):
        count = 0
        while self.isconnected():  # Ensure just one instance.
            await asyncio.sleep(1)  # Quick response to outage.
            count += 1
            count %= 20
            if not count:
                gc.collect()
                print('RAM free {} alloc {}'.format(gc.mem_free(), gc.mem_alloc()))

    def isconnected(self):
        if self._in_connect:  # Disable low-level check during .connect()
            return True
        if self._isconnected and not self._interface.isconnected():  # It's going down.
            self._reconnect()
        return self._isconnected

    def _reconnect(self):  # Schedule a reconnection if not underway.
        if self._isconnected:
            self._isconnected = False
            self.close()

    # Await broker connection.
    async def _connection(self):
        while not self._isconnected:
            await asyncio.sleep(1)

    # Scheduled on 1st successful connection. Runs forever maintaining wifi and
    # broker connection. Must handle conditions at edge of WiFi range.
    async def _keep_connected(self):
        while self._has_connected:
            if self.isconnected():  # Pause for 1 second
                await asyncio.sleep(1)
                gc.collect()
            else:
                if not await self._interface.reconnect():
                    continue
                if not self._has_connected:  # User has issued the terminal .disconnect()
                    self.dprint('Disconnected, exiting _keep_connected')
                    break
                try:
                    await self.connect()
                    # Now has set ._isconnected and scheduled _connect_handler().
                    self.dprint('Reconnect OK!')
                except OSError as e:
                    self.dprint('Error in reconnect.', e)
                    # Can get ECONNABORTED or -1. The latter signifies no or bad CONNACK received.
                    self.close()  # Disconnect and try again.
                    self._in_connect = False
                    self._isconnected = False
        self.dprint('Disconnected, exited _keep_connected')

    async def subscribe(self, topic, qos=0):
        qos_check(qos)
        while 1:
            await self._connection()
            try:
                return await super().subscribe(topic, qos)
            except OSError:
                pass
            self._reconnect()  # Broker or WiFi fail.

    async def publish(self, topic, msg, retain=False, qos=0):
        qos_check(qos)
        while 1:
            await self._connection()
            try:
                return await super().publish(topic, msg, retain, qos)
            except OSError:
                pass
            self._reconnect()  # Broker or WiFi fail.
