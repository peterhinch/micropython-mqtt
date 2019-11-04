# Author: Kevin Köck
# Copyright Kevin Köck 2019 Released under the MIT license
# Created on 2019-11-04

__updated__ = "2019-11-04"
__version__ = "0.1"

from .mqtt_as import MQTTClient as _MQTTClient
import uasyncio as asyncio
import time


class MQTTClient(_MQTTClient):
    _ops_coros = [None] * 10

    async def publish(self, topic, msg, retain=False, qos=0, timeout=None, await_connection=True):
        return await self._preprocessor(super().publish, topic, msg, retain, qos,
                                        timeout=timeout, await_connection=await_connection)

    async def subscribe(self, topic, qos=0, timeout=None, await_connection=True):
        await self._preprocessor(super().subscribe, topic, qos, timeout=timeout,
                                 await_connection=await_connection)

    async def unsubscribe(self, topic, timeout=None, await_connection=False):
        # with clean sessions a connection loss is basically a successful unsubscribe
        return await self._preprocessor(super().unsubscribe, topic, timeout=timeout,
                                        await_connection=False)

    # Await broker connection. Subclassed to reduce canceling time from 1s to 50ms
    async def _connection(self):
        while not self._isconnected:
            await asyncio.sleep_ms(50)

    async def _operationTimeout(self, coro, *args, slot):
        try:
            await coro(*args)
        finally:
            self._ops_coros[slot] = None

    async def _preprocessor(self, coroutine, *args, timeout=None, await_connection=True):
        start = time.ticks_ms()
        slot = None
        coro = None
        try:
            while timeout is None or time.ticks_diff(time.ticks_ms(), start) < timeout * 1000:
                if not await_connection and not self._isconnected:
                    return False
                if slot is None:
                    # wait for slot in queue
                    for i, c in enumerate(self._ops_coros):
                        if c is None:
                            slot = i
                            break
                elif slot and self._ops_coros[slot] is coro is None:
                    # create task
                    coro = self._operationTimeout(coroutine, *args, slot=slot)
                    asyncio.get_event_loop().create_task(coro)
                    self._ops_coros[slot] = coro
                elif self._ops_coros[slot] != coro:
                    # Slot either None or already new coro assigned.
                    # Means the operation finished successfully.
                    return True
                await asyncio.sleep_ms(20)
            self.dprint("timeout on", args)
        except asyncio.CancelledError:
            raise  # the caller of this coro should be cancelled too
        finally:
            if coro and self._ops_coros[slot] == coro:
                # coro still active, cancel it
                async with self.lock:
                    asyncio.cancel(coro)
                # self._ops_coros[slot] = None  is done by finally in _operationTimeout
                return False
            # else: returns return value during process
        return False
