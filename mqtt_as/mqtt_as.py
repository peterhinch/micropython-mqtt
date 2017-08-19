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
_SOCKET_POLL_DELAY = const(5)  # 100ms added greatly to publish latency
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
        # Do this once to prevent blocking during later internet outage:
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
        will=None, clean_init=True, clean=True, max_repubs=4):
        self._response_time = response_time * 1000  # Repub if no PUBACK received (ms).
        self._cb = subs_cb
        self._wifi_handler = wifi_coro
        self._connect_handler = connect_coro
        if will is None:
            self._lw_topic = False
        else:
            self.set_last_will(*will)
        self._clean_init = clean_init  # clean_session state on first connection
        self._clean = clean  # clean_session state on reconnect
        self._max_repubs = max_repubs

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

    async def _as_read(self, n, sock=None):  # OSError caught by superclass
        if sock is None:
            sock = self.sock
        data = b''
        t = ticks_ms()
        while len(data) < n:
            if self.timeout(t) or not self.isconnected():
                raise OSError(-1)
            msg = sock.read(n - len(data))
            if msg == b'':  # Connection closed by host (?)
                raise OSError(-1)
            if msg is not None:  # data received
                data = b''.join((data, msg))
                t = ticks_ms()
                self.last_rx = ticks_ms()
            await asyncio.sleep_ms(_SOCKET_POLL_DELAY)
        return data

    async def _as_write(self, bytes_wr, length=0, sock=None):
        if sock is None:
            sock = self.sock
        if length:
            bytes_wr = bytes_wr[:length]
        t = ticks_ms()
        while bytes_wr:
            if self.timeout(t) or not self.isconnected():
                raise OSError(-1)
            n = sock.write(bytes_wr)
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
        self.sock = socket.socket()
        self.sock.setblocking(False)
        try:
            self.sock.connect(self.addr)
        except OSError as e:
            # https://forum.micropython.org/viewtopic.php?f=16&t=3608&p=20942#p20942
            if e.args[0] not in [uerrno.EINPROGRESS, uerrno.ETIMEDOUT]:
                raise  # from uasyncio __init__.py open_connection()
        await asyncio.sleep_ms(_DEFAULT_MS)
        self.dprint('Connecting to broker.')
        if self.ssl:
            import ussl
            self.sock = ussl.wrap_socket(self.sock, **self.ssl_params)
        premsg = bytearray(b"\x10\0\0\0\0\0")
        msg = bytearray(b"\x04MQTT\x04\0\0\0")

        sz = 10 + 2 + len(self.client_id)
        msg[6] = clean << 1
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
        # read causes ECONNABORTED if broker is out; triggers a reconnect.
        resp = await self._as_read(4)
        self.dprint('Connected to broker.')
        if resp[3] != 0 or resp[0] != 0x20 or resp[1] != 0x02:
            raise OSError(-1)

    async def _ping(self):
        async with self.lock:
            await self._as_write(b"\xc0\0")

    async def broker_up(self):  # Test broker connectivity
        tlast = self.last_rx
        if ticks_diff(ticks_ms(), tlast) < 1000:
            return True
        try:
            await self._ping()
        except OSError:
            return False
        t = ticks_ms()
        while not self.timeout(t):
            await asyncio.sleep_ms(100)
            if ticks_diff(self.last_rx, tlast) > 0:  # Response received
                return True
        return False

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
                if self.timeout(t) or not self.isconnected():
                    break  # Must repub or bail out
            else:
                return  # PID's match. All done.
            # No match
            if count >= self._max_repubs or not self.isconnected():
                raise OSError(-1)  # Subclass to re-publish with new PID
            async with self.lock:
                await self._publish(topic, msg, retain, qos, dup = 1)
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

    # Can raise OSError if WiFi fails. Subclass traps
    async def subscribe(self, topic, qos):
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
        self._isconnected = False  # Current connection state
        keepalive *= 1000  # ms
        self._ping_interval = keepalive // 4 if keepalive else 20000
        self._in_connect = False
        self._has_connected = False  # Define 'Clean Session' value to use.

    async def connect(self):
        self._in_connect = True  # Disable low level ._isconnected check
        clean = self._clean if self._has_connected else self._clean_init
        await self._connect(clean)
        # If we get here without error broker/LAN must be up.
        self._isconnected = True
        self._in_connect = False  # Low level code can now check connectivity.
        loop = asyncio.get_event_loop()
        loop.create_task(self._wifi_handler(True))  # User handler.
        if not self._has_connected:
            self._has_connected = True  # Use normal clean flag on reconnect.
            loop.create_task(self._keep_connected())  # Runs forever.

        loop.create_task(self._handle_msg())  # Tasks quit on connection fail.
        loop.create_task(self._keep_alive())
        if self.DEBUG:
            loop.create_task(self._memory())
        loop.create_task(self._connect_handler(self))  # User handler.

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
            elif pings_due >= 1:
                try:
                    await self._ping()
                except OSError:
                    break
            await asyncio.sleep(1)
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
        if self._isconnected and not self.sta_if.isconnected():  # It's going down.
            self._reconnect()
        return self._isconnected

    def _reconnect(self):  # Schedule a reconnection if not underway.
        if self._isconnected:
            self._isconnected = False
            self.sock.close()
            loop = asyncio.get_event_loop()
            loop.create_task(self._wifi_handler(False))  # User handler.

    # Await broker connection. 
    async def _connection(self):
        while not self._isconnected:
            await asyncio.sleep(1)

    # Scheduled on 1st successful connection. Runs forever maintaining wifi and
    # broker connection. Must handle conditions at edge of WiFi range.
    async def _keep_connected(self):
        s = self.sta_if
        while True:
            if self.isconnected():
                await asyncio.sleep(1)
                gc.collect()
            else:
                s.disconnect()
                await asyncio.sleep(1)
                s.connect()
                await asyncio.sleep(1)
                while s.status() == network.STAT_CONNECTING:
                    await asyncio.sleep(1)  # Break out on fail or success
                # Ensure connection stays up for a few secs.
                t = ticks_ms()
                while ticks_diff(ticks_ms(), t) < 5000:
                    if not s.isconnected():
                        break  # Outer loop disconnects and tries again.
                    await asyncio.sleep(1)
                else:
                    # Timer expired: assumed reasonably reliable. Try reconnect.
                    # Note ._isconnected is False at this point.
                    try:
                        await self.connect()
                        # Now has set ._isconnected and scheduled _connect_handler().
                        self.dprint('Reconnect OK!')
                    except OSError as e:
                        self.dprint('Error in reconnect', e)  # Can get ECONNABORTED or -1.
                        self.sock.close()  # Disconnect and try again.
                        self._in_connect = False
                        self._isconnected = False

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
                self.dprint('Pub:', topic, msg, retain, qos)
                return await super().publish(topic, msg, retain, qos)
            except OSError:
                pass
            self.dprint('dup failed. Reconnect and repub with new PID.')
            self._reconnect()  # Broker or WiFi fail.
