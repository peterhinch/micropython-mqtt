from mqtt_as import MQTTClient as _MQTTClient
import time
import uasyncio as asyncio


class MQTTClient(_MQTTClient):
    _pub_coro = None

    # Await broker connection. Subclassed to reduce canceling time from 1s to 50ms
    async def _connection(self):
        while not self._isconnected:
            await asyncio.sleep_ms(50)

    async def _publishTimeout(self, topic, msg, retain, qos):
        try:
            await super().publish(topic, msg, retain, qos)
        except asyncio.CancelledError:
            pass
        finally:
            self._pub_coro = None

    async def publish(self, topic, msg, retain=False, qos=0, timeout=None):
        coro = None
        start = time.ticks_ms()
        while timeout is None or time.ticks_diff(time.ticks_ms(), start) < timeout:
            if self._pub_coro is None and coro is None:
                coro = self._publishTimeout(topic, msg, retain, qos)
                asyncio.get_event_loop().create_task(coro)
                self._pub_coro = coro
            elif coro is not None:
                if self._pub_coro != coro:
                    return  # published
            await asyncio.sleep_ms(20)
        if coro is not None:
            async with self.lock:
                asyncio.cancel(coro)
                return
