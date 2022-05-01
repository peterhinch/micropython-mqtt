# mqtt_as_queue.py Implementation of a message queue for publishing

# (C) Copyright 2022 Andreas Philipp.
# Released under the MIT licence.

# This extension of the class mqtt_as contains a message queue. The queued 
# messages can then be sent
# - one (by one)
# - all of them (once) or
# - all of them by a task in background

from mqtt_as import MQTTClient as _MQTTClient
import uasyncio

class MQTTClient(_MQTTClient):
    message_queue = []

    # Add message to the queue
    def queue_message(self, topic, msg, retain=False, qos=0):
        self.message_queue.append((topic, msg, retain, qos))

    # Publish one message from the queue
    async def publish_one(self):
        (topic, msg, retain, qos) = self.message_queue.pop(0)
        await self.publish(topic, msg, retain, qos)

    # Publish all messages in the queue
    async def publish_queue(self):
        while len(self.message_queue) > 0:
            await self.publish_one()
            await uasyncio.sleep_ms(100)
    
    # Publish all messages (run as task)
    async def publish_task(self):
        while True:
            await self.publish_queue()
            await uasyncio.sleep_ms(100)
