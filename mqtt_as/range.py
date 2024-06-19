# range.py Test of asynchronous mqtt client with clean session False.
# (C) Copyright Peter Hinch 2017-2024.
# Released under the MIT licence.

# Now uses the event interface

# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers

# This demo is for wireless range tests. If OOR the red WiFi ON LED will go out.
# In range the blue LED will pulse for each received message.
# Uses clean sessions to avoid backlog when OOR.

# red LED: ON == WiFi OK
# blue LED pulse == message received
# Publishes connection statistics.

from mqtt_as import MQTTClient
from mqtt_local import wifi_led, blue_led, config
import uasyncio as asyncio

TOPIC = "shed"  # For demo publication and last will use same topic

outages = 0


async def pulse():  # This demo pulses blue LED each time a subscribed msg arrives.
    blue_led(True)
    await asyncio.sleep(1)
    blue_led(False)


async def messages(client):
    async for topic, msg, retained in client.queue:
        print(f'Topic: "{topic.decode()}" Message: "{msg.decode()}" Retained: {retained}')
        asyncio.create_task(pulse())


async def down(client):
    global outages
    while True:
        await client.down.wait()  # Pause until connectivity changes
        client.down.clear()
        wifi_led(False)
        outages += 1
        print("WiFi or broker is down.")


async def up(client):
    while True:
        await client.up.wait()
        client.up.clear()
        wifi_led(True)
        print("We are connected to broker.")
        await client.subscribe("foo_topic", 1)


async def main(client):
    try:
        await client.connect()
    except OSError:
        print("Connection failed.")
        return
    for task in (up, down, messages):
        asyncio.create_task(task(client))
    n = 0
    while True:
        await asyncio.sleep(5)
        print("publish", n)
        # If WiFi is down the following will pause for the duration.
        await client.publish(
            TOPIC, "{} repubs: {} outages: {}".format(n, client.REPUB_COUNT, outages), qos=1
        )
        n += 1


# Define configuration
config["will"] = (TOPIC, "Goodbye cruel world!", False, 0)
config["keepalive"] = 120
config["queue_len"] = 1  # Use event interface with default queue

# Set up client. Enable optional debug statements.
MQTTClient.DEBUG = True
client = MQTTClient(config)

try:
    asyncio.run(main(client))
finally:  # Prevent LmacRxBlk:1 errors.
    client.close()
    blue_led(True)
    asyncio.new_event_loop()
