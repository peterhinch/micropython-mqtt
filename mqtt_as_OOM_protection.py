# Author: Kevin Köck
# Copyright Kevin Köck 2019 Released under the MIT license
# Created on 2019-10-28 

__updated__ = "2019-10-28"
__version__ = "0.1"

from .mqtt_as import MQTTClient as _MQTTClient, ticks_ms, BUSY_ERRORS, asyncio, _SOCKET_POLL_DELAY
import gc


class MQTTClient(_MQTTClient):
    async def _as_read(self, n, sock=None):  # OSError caught by superclass
        if sock is None:
            sock = self._sock
        data = b''
        t = ticks_ms()
        r = 0
        while r < n:
            if self._timeout(t) or not self.isconnected():
                raise OSError(-1)
            nr = (n - r) if (n - r) < 200 else 200
            try:
                msg = sock.read(nr)
                if msg is not None:
                    r += len(msg)
            except OSError as e:  # ESP32 issues weird 119 errors here
                msg = None
                if e.args[0] not in BUSY_ERRORS:
                    raise
            except MemoryError as e:
                # no way of knowing how many bytes were received so the rest would be
                # received later and lead to buffer overflows and keepalive timeout anyway
                # so best to terminate the connection
                raise OSError
            if msg == b'':  # Connection closed by host (?)
                raise OSError(-1)
            if msg is not None and data is not None:  # data received
                try:
                    data = b''.join((data, msg))
                except MemoryError as e:
                    data = None
                    gc.collect()
                t = ticks_ms()
                self.last_rx = ticks_ms()
            await asyncio.sleep_ms(0 if nr == 200 and msg is not None else _SOCKET_POLL_DELAY)
            # don't wait if receiving a big message in chunks but yield
            # to not block all other coroutines
        return data
