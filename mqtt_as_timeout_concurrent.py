# Author: Kevin Köck
# Copyright Kevin Köck 2019 Released under the MIT license
# Created on 2019-11-04

__updated__ = "2019-11-04"
__version__ = "0.2"

from micropython_mqtt_as.mqtt_as import MQTTClient as _MQTTClient
import uasyncio as asyncio
import time


class MQTTClient(_MQTTClient):
    _ops_coros = set()

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
            for obj in self._ops_coros:
                if obj[0] == slot:
                    self._ops_coros.discard(obj)
                    return

    async def _preprocessor(self, coroutine, *args, timeout=None, await_connection=True):
        start = time.ticks_ms()
        coro = None
        try:
            while timeout is None or time.ticks_diff(time.ticks_ms(), start) < timeout * 1000:
                if not await_connection and not self._isconnected:
                    return False
                elif coro is None:
                    # search for unused identifier
                    identifier = None
                    for i in range(1024):
                        found = False
                        for obj in self._ops_coros:
                            if obj[0] == i:
                                found = True
                                break
                        if not found:  # id unique
                            identifier = i
                            break
                    # create task
                    task = self._operationTimeout(coroutine, *args, slot=identifier)
                    asyncio.get_event_loop().create_task(task)
                    coro = (identifier, task)
                    self._ops_coros.add(coro)
                elif coro not in self._ops_coros:
                    # coro removed, so operation was successful
                    self.dprint("Success on", args)
                    return True
                await asyncio.sleep_ms(20)
            self.dprint("timeout on", args)
        except asyncio.CancelledError:
            raise  # the caller of this coro should be cancelled too
        finally:
            if coro and coro in self._ops_coros:
                # coro still active, cancel it
                async with self.lock:
                    asyncio.cancel(coro[1])
                # self._ops_coros.discard(coro)  is done by finally in _operationTimeout
                return False
            # else: returns return value during process, which is True in case it was successful
        return False
