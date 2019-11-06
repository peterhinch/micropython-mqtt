# Author: Kevin Köck
# Copyright Kevin Köck 2019 Released under the MIT license
# Created on 2019-11-05 

__updated__ = "2019-11-06"
__version__ = "0.1"

try:
    from micropython_mqtt_as.mqtt_as import MQTTClient as _MQTTClient
except ImportError:
    from .mqtt_as import MQTTClient as _MQTTClient
import uasyncio as asyncio
import time


###
# wait_for for official uasyncio from https://github.com/kevinkk525/micropython_uasyncio_extension
###
class TimeoutError(Exception):
    pass


asyncio.TimeoutError = TimeoutError


async def wait_for(coro, timeout):
    return await wait_for_ms(coro, timeout * 1000)


async def wait_for_ms(coro, timeout):
    canned = False
    t = time.ticks_ms()

    async def killer():
        nonlocal canned
        while time.ticks_diff(time.ticks_ms(), t) < timeout:
            await asyncio.sleep(0)  # keeps killer in runq, leaves more slots in waitq
        asyncio.cancel(coro)
        canned = True  # used to identify if killer cancelled coro or got cancelled
        # because the CancelledError will also be raised in line 33.

    kill = killer()
    asyncio.ensure_future(kill)
    try:
        res = await coro
    except asyncio.CancelledError:
        if canned:  # coro got canceled, not wait_for
            if asyncio.DEBUG and __debug__:
                asyncio.log.debug("Coro %s cancelled in wait_for", coro)
            raise TimeoutError
        if asyncio.DEBUG and __debug__:
            asyncio.log.debug("Wait_for got cancelled awaiting %s", coro)
        raise
    except Exception:
        raise
    else:
        if canned:
            if asyncio.DEBUG and __debug__:
                asyncio.log.debug("Coro %s cancelled in wait_for but caught Exception", coro)
            raise TimeoutError
    finally:
        asyncio.cancel(kill)
    return res


asyncio.wait_for = wait_for
asyncio.wait_for_ms = wait_for_ms


###

class MQTTClient(_MQTTClient):

    # Await broker connection. Subclassed to reduce canceling time from 1s to 50ms
    async def _connection(self):
        while not self._isconnected:
            await asyncio.sleep_ms(50)

    async def _killer(self, coro):
        done = False
        res = None  # since mqtt_as doesn't return on success, None is success

        async def op():
            try:
                res = await coro
            finally:
                nonlocal done
                done = True

        task = op()
        asyncio.ensure_future(task)
        try:
            while not done:
                await asyncio.sleep(0)  # keep on runq
        except asyncio.CancelledError:
            async with self.lock:
                # print("canceled with lock")
                asyncio.cancel(task)
        return res

    async def publish(self, topic, msg, retain=False, qos=0, timeout=None):
        if timeout:
            try:
                return await asyncio.wait_for(
                    self._killer(super().publish(topic, msg, retain, qos)), timeout)
            except asyncio.TimeoutError:
                return False
        else:
            return await super().publish(topic, msg, retain, qos)

    async def subscribe(self, topic, qos=0, timeout=None):
        if timeout:
            try:
                return await asyncio.wait_for(
                    self._killer(super().subscribe(topic, qos)), timeout)
            except asyncio.TimeoutError:
                return False
        else:
            return await super().subscribe(topic, qos)

    async def unsubscribe(self, topic, timeout=None):
        if timeout:
            try:
                return await asyncio.wait_for(
                    self._killer(super().unsubscribe(topic)), timeout)
            except asyncio.TimeoutError:
                return False
        else:
            return await super().unsubscribe(topic)
