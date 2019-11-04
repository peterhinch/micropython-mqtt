# mqtt_as_timeout.py Implementation of a timeout on publication.

# (C) Copyright 2019 Kevin Köck.
# Released under the MIT licence.

# This solution detects the case where a publication is delayed by lack of
# connectivity and cancels it if the delay exceeds a timeout.

# Note that it blocks other attempts at publication while waiting for a PUBACK,
# counter to the normal operation of the module. A solution capable of handling
# concurrent qos == 1 publications would require a set instance containing coros.

# It incorporates a workround for the bug in uasyncio V2 whereby cancellation
# is deferred if a task is waiting on a sleep command.
# For these reasons it was not included in the mqtt_as module.

# The occurrence of a timeout does not guarantee non-reception of the message:
# connectivity loss may occur between reception by the broker and reception of
# CONNACK by the client. However in this case the message would be received in
# a timely fashion.

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
