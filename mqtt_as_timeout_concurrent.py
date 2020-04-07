# Author: Kevin Köck
# Copyright Kevin Köck 2019 Released under the MIT license
# Created on 2019-11-04

__updated__ = "2020-04-01"
__version__ = "0.4"

try:
    from micropython_mqtt_as.mqtt_as import MQTTClient as _MQTTClient
except ImportError:
    from .mqtt_as import MQTTClient as _MQTTClient
import uasyncio as asyncio
import time


class MQTTClient(_MQTTClient):
    # operations return False is connection was lost and await_connection==False.
    # operations return True if the operation was finished (mqtt_as doesn't return anything)
    # operations raise asyncio.TimeoutError on timeout
    # operations raise asyncio.CancelledError if the caller task got cancelled

    async def _waiter(self, coro, timeout, await_connection):
        # using _waiter even without a timeout as it ensures proper cancellation with self.lock
        done = False

        async def op():
            nonlocal done
            try:
                await coro
                done = True
            except Exception as e:
                done = e

        task = asyncio.create_task(op())
        start = time.ticks_ms()
        try:
            while not done:
                if not await_connection and not self._isconnected:
                    self.dprint("Connection lost")
                    return False
                elif timeout and time.ticks_diff(time.ticks_ms(), start) > timeout * 1000:
                    self.dprint("timeout in operation")
                    raise asyncio.TimeoutError
                await asyncio.sleep_ms(40)
            task = None  # Task finished. finally doesn't need to cancel it.
            if isinstance(done, Exception):
                raise done
            else:
                return done
        except asyncio.CancelledError:
            # operation got cancelled externally, finally: will cancel the task
            raise
        finally:
            if task:
                async with self.lock:
                    self.dprint("canceled with lock")
                    task.cancel()

    async def publish(self, topic, msg, retain=False, qos=0, timeout=None, await_connection=True):
        if not await_connection and not self._isconnected:
            return False
        return await self._waiter(super().publish(topic, msg, retain, qos), timeout,
                                  await_connection)

    async def subscribe(self, topic, qos=0, timeout=None, await_connection=True):
        if not await_connection and not self._isconnected:
            return False
        return await self._waiter(super().subscribe(topic, qos), timeout, await_connection)

    async def unsubscribe(self, topic, timeout=None, await_connection=True):
        if not await_connection and not self._isconnected:
            return False
        return await self._waiter(super().unsubscribe(topic), timeout, await_connection)
