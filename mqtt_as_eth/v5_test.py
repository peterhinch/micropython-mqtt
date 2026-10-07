# v5_test.py Test mqtt_as_eth on wired Ethernet hardware: Wiznet 5500 NIC.

# (C) Copyright Peter Hinch 2017-2026.
# Released under the MIT licence.

# Tests V5 properties
# Demo does not use mqtt_local.py
# Publishes to topic "shed", subscribes to "foo_topic"

# ./pubtest
# mosquitto_pub -h 192.168.0.10 -t foo_topic -m "gordon bennett" -q 1
# mosquitto_sub -h 192.168.0.10 -t shed
from mqtt_as_eth import MQTTClient, config
import asyncio
import network
import time

TOPIC = "shed"  # For demo publication and last will use same topic

outages = 0


async def messages(client):
    async for topic, msg, retained, properties in client.queue:
        print(
            f'Topic: "{topic.decode()}" Message: "{msg.decode()}" Retained: {retained} Properties: {properties}'
        )


async def down(client):
    global outages
    while True:
        await client.down.wait()  # Pause until connectivity changes
        client.down.clear()
        outages += 1
        print("WiFi or broker is down.")


async def up(client):
    while True:
        await client.up.wait()
        client.up.clear()
        print("We are connected to broker.")
        await client.subscribe("foo_topic", 1)


async def main(client):
    if not nic.isconnected():
        print("No Ethernet connection.")
    try:
        await client.connect()
    except OSError:
        print("Connection failed.")
        return
    for task in (up, down, messages):
        asyncio.create_task(task(client))
    properties = {
        0x26: {"value": "test"},  # User Property (UTF-8 string pair)
        0x09: b"correlation_data",  # Correlation Data (binary)
        0x08: "response_topic",  # Response Topic (UTF-8 string)
        0x02: 60,  # Message Expiry Interval (integer)
    }

    n = 0
    while True:
        await asyncio.sleep(5)
        print("publish", n)
        # If LAN is down the following will pause for the duration.
        await client.publish(
            TOPIC,
            f"{n} repubs: {client.REPUB_COUNT} outages: {outages}",
            retain=False,
            qos=1,
            properties=properties,
        )
        n += 1


# Define configuration
config["server"] = "192.168.0.10"
config["will"] = (TOPIC, "Goodbye cruel world!", False, 0)
config["keepalive"] = 120
config["queue_len"] = 1  # Use event interface with default queue
config["mqttv5"] = True
config["mqttv5_con_props"] = {
    0x11: 3600,  # Session Expiry Interval
}

# Bring up LAN
nic = network.WIZNET5K()
nic.active(False)
nic.active(True)
print("Waiting for LAN...")
while not nic.isconnected():
    time.sleep(1)
print("LAN OK:", nic.ifconfig())

# Set up client. Enable optional debug statements.
MQTTClient.DEBUG = True
client = MQTTClient(config)

try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()
