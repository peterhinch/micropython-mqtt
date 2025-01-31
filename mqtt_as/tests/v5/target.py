# tests/v5/target.py Runs on device under test. Challenged by test.py

# (C) Copyright Peter Hinch 2025.
# Released under the MIT licence.

# Run with
# mpremote mount . exec "import mqtt_as.tests.v5.target"


# Create subscription to foo_topic with:
# mosquitto_pub -h 192.168.0.10 -t control -m '["subscribe","foo_topic", ""]' -q 1
# Publish to foo_topic:
# mosquitto_pub -h 192.168.0.10 -t foo_topic -m test_message -q 1
# Check response:
# mosquitto_sub -h 192.168.0.10 -t response
# Unsubscribe with
# mosquitto_pub -h 192.168.0.10 -t control -m '["unsubscribe","foo_topic", ""]' -q 1
# Cause target to publish to my_topic
# mosquitto_pub -h 192.168.0.10 -t control -m '["publish", "my_topic", "hello there"]' -q 1

# Receive publications which are a response to a received message
# mosquitto_sub -h 192.168.0.10 -t response

from mqtt_as import MQTTClient, RP2

if RP2:
    from sys import implementation
from mqtt_local import wifi_led, blue_led, config
import asyncio
import gc
import json


async def pulse():  # This demo pulses blue LED each time a subscribed msg arrives.
    blue_led(True)
    await asyncio.sleep(1)
    blue_led(False)


# Messages from foo_topic and sub_topic; the latter control subscription to the former.
async def messages():
    async for topic, msg, retained, properties in client.queue:
        topic = topic.decode()
        message = msg.decode()
        print(
            f'Topic: "{topic}" Message: "{message}" Retained: {retained} Properties: {properties}'
        )
        asyncio.create_task(pulse())
        if topic == "control":
            q = json.loads(message)
            cmd, tpc, msg = q[:3]
            props = None if len(q) == 3 else q[3]

            if props is not None:  # Fix up the way JSON mangles ints. Only fixes keys!
                props = {int(k): props[k] for k in props.keys()}
            if cmd == "subscribe":
                await client.subscribe(tpc, 1)
                print(f"Subscribed to {tpc} ******")
            elif cmd == "publish":
                await client.publish(tpc, msg, qos=1, properties=props)
                print(f"Published: topic {tpc} message {msg} ******")
            elif cmd == "unsubscribe":
                await client.unsubscribe(tpc)
                print(f"Unsubscribed from {tpc} ******")
        else:
            await client.publish("response", json.dumps([topic, message, properties]), qos=1)
            print(f"Received: topic {topic} message {message} ******")


async def down():
    while True:
        await client.down.wait()  # Pause until connectivity changes
        client.down.clear()
        wifi_led(False)
        print("WiFi or broker is down.")


async def up():
    while True:
        await client.up.wait()
        client.up.clear()
        wifi_led(True)
        print("We are connected to broker.")
        await client.subscribe("control", 1)


async def main():
    try:
        await client.connect(quick=True)
    except OSError:
        print("Connection failed.")
        return
    await asyncio.gather(up(), down(), messages())


# Define configuration
config["keepalive"] = 120
config["queue_len"] = 4  # Use event interface
config["mqttv5"] = True

# Set up client. Enable optional debug statements.
MQTTClient.DEBUG = True
client = MQTTClient(config)

try:
    asyncio.run(main())
finally:
    client.close()
    blue_led(True)
    asyncio.new_event_loop()
