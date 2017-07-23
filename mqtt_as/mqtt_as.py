# mqtt_as.py Asynchronous version of umqt.robust
# (C) Copyright Peter Hinch 2017.
# Released under the MIT licence.

import gc
import usocket as socket
import ustruct as struct
gc.collect()
from ubinascii import hexlify
import uasyncio as asyncio
gc.collect()
from utime import ticks_ms, ticks_diff
import uerrno
gc.collect()
from micropython import const
import network
gc.collect()

class MQTTException(Exception):
    pass

def newpid(pid):
    return pid + 1 if pid < 65535 else 1

def qos_check(qos):
    if not (qos == 0 or qos == 1):
        raise ValueError('Only qos 0 and 1 are supported.')

# Default short delay for good SynCom throughput (avoid sleep(0) with SynCom).
_DEFAULT_MS = const(20)

# Default "do little" coro for optional user replacement
async def eliza(*_):  # e.g. via set_wifi_handler(coro): see test program
    await asyncio.sleep_ms(_DEFAULT_MS)

class Lock():
    def __init__(self):
        self._locked = False

    async def __aenter__(self):
        while True:
            if self._locked:
                await asyncio.sleep_ms(_DEFAULT_MS)
            else:
                self._locked = True
                break

    async def __aexit__(self, *args):
        self._locked = False
        await asyncio.sleep_ms(_DEFAULT_MS)


# MQTT_base class. Handles MQTT protocol on the basis of a good connection.
# Exceptions from connectivity failures are handled by MQTTClient subclass.
class MQTT_base:

    REPUB_COUNT = 0  # TEST
    DEBUG = False

    def __init__(self, mqtt_args, client_id, server, port, user, password, keepalive, ssl, ssl_params):
        if port == 0:
            port = 8883 if ssl else 1883
        self.client_id = client_id
        self.sock = None
        self.addr = socket.getaddrinfo(server, port)[0][-1]
        self.ssl = ssl
        self.ssl_params = ssl_params
        self.pid = 0
        self.rcv_pid = 0
        self.suback = False
        self.user = user
        self.pswd = password
        if keepalive >= 65536:
            raise ValueError('Invalid keepalive time')
        self.keepalive = keepalive
        self._response_time = 10000  # Repub if no PUBACK received (ms).

        self.sta_if = network.WLAN(network.STA_IF)
        self.sta_if.active(True)
        self.last_rx = ticks_ms()  # Time of last communication from broker
        self.lock = Lock()
        self.setup(**mqtt_args)

    def setup(self, response_time=10, subs_cb=lambda *_ : None, wifi_coro=eliza, connect_coro=eliza,
        will=None, clean_init=True, clean=True, max_repubs=4, reconn_delay=5):
        self._response_time = response_time * 1000  # Repub if no PUBACK received (ms).
        self._cb = subs_cb
        self._wifi_handler = wifi_coro
        self._connect_handler = connect_coro
        if will is None:
            self._lw_topic = False
        else:
            self.set_last_will(*will)
        self._cs_1 = clean_init  # clean_session state on first connection
        self._cs = clean  # clean_session state on reconnect
        self._max_repubs = max_repubs
        self._reconn_delay = reconn_delay  # secs
        self._in_connect = False
        self._has_connected = False

    def set_last_will(self, topic, msg, retain=False, qos=0):
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

    def timeout(self, t):
        return ticks_diff(ticks_ms(), t) > self._response_time

    async def _as_read(self, n):  # OSError caught by superclass
        data = b''
        t = ticks_ms()
        while len(data) < n:
            if self.timeout(t) or not (self._in_connect or self._wifi_ok):
                raise OSError(-1)
            msg = self.sock.read(n - len(data))
            if msg == b'':  # Connection closed by host (?)
                raise OSError(-1)
            if msg is not None:  # data received
                data = b''.join((data, msg))
                t = ticks_ms()
                self.last_rx = ticks_ms()
            await asyncio.sleep_ms(100)
        return data

    async def _as_write(self, bytes_wr, length=0):
        if length:
            bytes_wr = bytes_wr[:length]
        t = ticks_ms()
        while bytes_wr:
            if self.timeout(t) or not (self._in_connect or self._wifi_ok):
                raise OSError(-1)
            n = self.sock.write(bytes_wr)
            if n:
                t = ticks_ms()
            bytes_wr = bytes_wr[n:]
            await asyncio.sleep_ms(100)

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

    async def connect(self):
        self._in_connect = True
        self.sock = socket.socket()
        self.sock.setblocking(False)
        try:
            self.sock.connect(self.addr)
        except OSError as e:
            if e.args[0] != uerrno.EINPROGRESS:
                raise  # from uasyncio __init__.py open_connection()
        await asyncio.sleep_ms(_DEFAULT_MS)
        self.dprint('Connected to broker')
        if self.ssl:
            import ussl
            self.sock = ussl.wrap_socket(self.sock, **self.ssl_params)
        premsg = bytearray(b"\x10\0\0\0\0\0")
        msg = bytearray(b"\x04MQTT\x04\0\0\0")

        sz = 10 + 2 + len(self.client_id)
        msg[6] = (self._cs if self._has_connected else self._cs_1) << 1
        if self.user is not None:
            sz += 2 + len(self.user) + 2 + len(self.pswd)
            msg[6] |= 0xC0
        if self.keepalive:
            msg[7] |= self.keepalive >> 8
            msg[8] |= self.keepalive & 0x00FF
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
        await self._send_str(self.client_id)
        if self._lw_topic:
            await self._send_str(self._lw_topic)
            await self._send_str(self._lw_msg)
        if self.user is not None:
            await self._send_str(self.user)
            await self._send_str(self.pswd)
        resp = await self._as_read(4)
        if resp[3] != 0 or resp[0] != 0x20 or resp[1] != 0x02:
            raise OSError(-1)
        # If we get here without error must be up.
        await self._wifi_up()
        self._in_connect = False
        self._has_connected = True

        loop = asyncio.get_event_loop()
        loop.create_task(self._handle_msg())
        loop.create_task(self._keep_alive())
        if self.DEBUG:
            loop.create_task(self._memory())
        await self._connect_handler(self)  # Optional user handler

    async def _memory(self):
        count = 0
        while self.wifi_ok():  # Don't let instances accumulate
            await asyncio.sleep(1)  # detect brief outages
            count += 1
            count %= 20
            if not count:
                gc.collect()
                print('RAM free {} alloc {}'.format(gc.mem_free(), gc.mem_alloc()))

    async def _ping(self):
        await self._wifi()
        async with self.lock:
            await self._as_write(b"\xc0\0")

    def disconnect(self):
        try:
            self.sock.write(b"\xe0\0")
        except OSError:
            pass
        self.sock.close()

    def close(self):
        self.sock.close()

    # qos == 1: coro blocks until wait_msg gets correct PID.
    # If WiFi fails completely subclass re-publishes with new PID.
    async def publish(self, topic, msg, retain, qos):
        if qos:
            self.pid = newpid(self.pid)
            self.rcv_pid = 0
        async with self.lock:
            await self._publish(topic, msg, retain, qos, 0)
        if qos == 0:
            return

        count = 0
        while 1:  # Await PUBACK, republish on timeout
            t = ticks_ms()
            while self.pid != self.rcv_pid:
                await asyncio.sleep_ms(200)
                if self.timeout(t) or not self.wifi_ok():
                    break  # Must repub or bail out
            else:
                return  # PID's match. All done.
            # No match
            if count >= self._max_repubs or not self.wifi_ok():
                raise OSError(-1)  # Subclass to re-publish with new PID
            async with self.lock:
                self._publish(topic, msg, retain, qos, dup = 1)
            count += 1
            self.REPUB_COUNT += 1

    async def _publish(self, topic, msg, retain, qos, dup):
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
            struct.pack_into("!H", pkt, 0, self.pid)
            await self._as_write(pkt, 2)
        await self._as_write(msg)

    # Can raise OSError if WiFi fails. App should trap
    async def subscribe(self, topic, qos):
        await self._wifi()
        self.suback = False
        pkt = bytearray(b"\x82\0\0\0")
        self.pid = newpid(self.pid)
        struct.pack_into("!BH", pkt, 1, 2 + 2 + len(topic) + 1, self.pid)
        self.pkt = pkt
        async with self.lock:
            await self._as_write(pkt)
            await self._send_str(topic)
            await self._as_write(qos.to_bytes(1, "little"))

        t = ticks_ms()
        while not self.suback:
            await asyncio.sleep_ms(200)
            if self.timeout(t):
                raise OSError(-1)

    # Wait for a single incoming MQTT message and process it.
    # Subscribed messages are delivered to a callback previously
    # set by .setup() method. Other (internal) MQTT
    # messages processed internally.
    # Immediate return if no data available. Called from ._handle_msg().
    async def wait_msg(self):
        res = self.sock.read(1)  # Throws OSError on WiFi fail
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
            self.rcv_pid = rcv_pid[0] << 8 | rcv_pid[1]

        if op == 0x90:  # SUBACK
            resp = await self._as_read(4)
            if resp[1] != self.pkt[2] or resp[2] != self.pkt[3] or resp[3] == 0x80:
                raise OSError(-1)
            self.suback = True

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
        self._cb(topic, msg)
        if op & 6 == 2:
            pkt = bytearray(b"\x40\x02\0\0")  # Send PUBACK
            struct.pack_into("!H", pkt, 2, pid)
            await self._as_write(pkt)
        elif op & 6 == 4:
            raise OSError(-1)


# MQTTClient class. Handles issues relating to connectivity.

class MQTTClient(MQTT_base):

    def __init__(self, mqtt_args, client_id, server,*, port=0, user=None,
                 password=None, keepalive=0, ssl=False, ssl_params={}):
        super().__init__(mqtt_args, client_id, server, port, user, password,
                         keepalive, ssl, ssl_params)
        self._wifi_ok = False  # Current state
        self._wifi_connecting = False  # Prevent concurrent calls to connect()
        self._wifi_downed = False  # Ensure handler is called once only on down.
        keepalive *= 1000  # ms
        self._ping_interval = keepalive // 4 if keepalive else 20000

    # Launched by .connect().
    # Runs until ping failure or no response in keepalive period.
    # Keep broker alive MQTT spec 3.1.2.10 Keep Alive
    async def _keep_alive(self):
        ok = True
        while ok and self.sta_if.isconnected():
            await asyncio.sleep(1)
            pings_due = ticks_diff(ticks_ms(), self.last_rx) // self._ping_interval
            if pings_due >= 4:
                ok = False
                self.dprint('Reconnect: broker fail.')
            elif pings_due >= 1:
                try:
                    await self._ping()
                except OSError:
                    ok = False
        self._wifi_ok = False
        await self._wifi_down()

    # Launched by .connect(). Runs continuously with two aims
    # 1. Checking for incoming messages
    # 2. Detecting WiFi outages by regularly polling the socket. This will
    # throw an OSError causing the coro to quit
    async def _handle_msg(self):
        try:
            while self.wifi_ok():
                async with self.lock:
                    await self.wait_msg()  # Immediate return if no message
                await asyncio.sleep_ms(100)  # Let other activities get lock

        except OSError:
            pass
        self._wifi_ok = False
        await self._wifi_down()

    def wifi_ok(self):
        return self._wifi_ok and self.sta_if.isconnected()  # Fast response to outage

    async def _wifi_up(self):  # Called at successful completion of connect()
        self._wifi_ok = True
        self._wifi_downed = False
        await self._wifi_handler(True)  # Default handler just delays

    async def _wifi_down(self):
        if not self._wifi_downed:
            self._wifi_downed = True
            self.sock.close()
            await self._wifi_handler(False)

    # Establish a WiFi and broker connection if not available. Must
    # handle conditions at edge of WiFi range.
    async def _wifi(self):
        if self.wifi_ok():
            return
        if self._wifi_connecting:  # Another coro is establishing connection,
            while self._wifi_connecting:  # await its success.
                await asyncio.sleep(1)
            return
        # Need to establish a connection.
        self._wifi_connecting = True  # Lock out other coros
        s = self.sta_if
        while True:
            s.disconnect()
            await asyncio.sleep(1)
            s.connect()
            await asyncio.sleep(1)
            while s.status() == network.STAT_CONNECTING:
                await asyncio.sleep(1)  # Break out on fail or success
            # Ensure connection stays up for expected response time
            t = ticks_ms()
            while not self.timeout(t):
                if not s.isconnected():
                    break  # disconnect and try again
                await asyncio.sleep(1)
            else:  # Timer expired: assumed reasonably reliable. Try reconnect.
                if await self._reconnect():
                    break  # Success. wifi_ok() will now succeed.
        self._wifi_connecting = False

    async def _reconnect(self):
        try:
            await self.connect()
            # Calls self._wifi_up() and _connect_handler() on success
            self.dprint('Reconnect OK!')
        except OSError as e:
            self.dprint('Error in reconnect', e)  # Can get ECONNABORTED or -1. Ignore and retry.
            self.sock.close()
            await asyncio.sleep(self._reconn_delay)
            return False
        return True

    async def subscribe(self, topic, qos=0):
        qos_check(qos)
        while 1:
            await self._wifi()
            try:
                return await super().subscribe(topic, qos)
            except OSError:
                pass
            self._wifi_ok = False
            await self._wifi_down()

    async def publish(self, topic, msg, retain=False, qos=0):
        qos_check(qos)
        while 1:
            await self._wifi()
            try:
                return await super().publish(topic, msg, retain, qos)
            except OSError:
                pass
            self._wifi_ok = False
            await self._wifi_down()
