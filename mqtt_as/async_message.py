# async_message.py Test of asynchronous mqtt client with async Broker class
# (C) Copyright Peter Hinch 2024.
# Released under the MIT licence.

# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers


from mqtt_as import MQTTClient
from mqtt_local import wifi_led, blue_led, config
import asyncio
from primitives import Broker


# Direct incoming LED topic messages to led_handler
def led_handler(topic, message, led):
    led(message == "on")


broker = Broker()
broker.subscribe("blue_topic", led_handler, blue_led)
broker.subscribe("red_topic", led_handler, wifi_led)


# Set up MQTT
TOPIC = "shed"  # For demo publication and last will use same topic


async def messages(client):
    async for topic, msg, retained in client.queue:
        print(f'Topic: "{topic.decode()}" Message: "{msg.decode()}" Retained: {retained}')
        broker.publish(topic.decode(), msg.decode())


async def up(client):
    while True:
        await client.up.wait()
        client.up.clear()
        print("We are connected to broker.")
        await client.subscribe("blue_topic", 1)
        await client.subscribe("red_topic", 1)


async def main(client):
    try:
        await client.connect()
    except OSError:
        print("Connection failed.")
        return
    asyncio.create_task(up(client))
    asyncio.create_task(messages(client))
    n = 0
    while True:
        await asyncio.sleep(5)
        print("publish", n)
        # If WiFi is down the following will pause for the duration.
        await client.publish(TOPIC, f"Count = {n}", qos=1)
        n += 1


# Define configuration
config["keepalive"] = 120
config["queue_len"] = 1  # Use event interface with default queue

# Set up client. Enable optional debug statements.
MQTTClient.DEBUG = True
client = MQTTClient(config)

try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()
