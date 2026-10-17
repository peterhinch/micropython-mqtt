#!/usr/bin/env micropython

# eth_test.py Test mqtt_as_eth on wired Ethernet hardware: Wiznet 5500 NIC.

# (C) Copyright Peter Hinch 2017-2026.
# Released under the MIT licence.

# Demo does not use mqtt_local.py
# Publishes to topic "shed", subscribes to "foo_topic"

# ./pubtest
# mosquitto_pub -h 192.168.0.10 -t foo_topic -m "gordon bennett" -q 1
# mosquitto_sub -h 192.168.0.10 -t shed
# from mqtt_as_eth import MQTTClient, config, on_pc
from __init__ import MQTTClient, config, on_pc
import asyncio
if not on_pc:
    import network
import time

SUB_TOPIC = "foo_topic"
PUB_TOPIC = "shed"  # For demo publication and last will use same topic
SERVER = "192.168.0.10"

outages = 0


async def messages(client):
    async for topic, msg, retained in client.queue:
        print(f'Topic: "{topic.decode()}" Message: "{msg.decode()}" Retained: {retained}')


async def down(client):
    global outages
    while True:
        await client.down.wait()  # Pause until connectivity changes
        client.down.clear()
        outages += 1
        print("Network or broker is down.")


async def up(client):
    while True:
        await client.up.wait()
        client.up.clear()
        print(f"We are connected to broker {config['server']} and are subscribing to {SUB_TOPIC}.")
        await client.subscribe(SUB_TOPIC, 1)


async def main(client):
    if not on_pc and not nic.isconnected():
        print("No Ethernet connection.")
    try:
        await client.connect()
    except OSError as exc:
        print("Connection failed:", exc)
        return
    # await client.subscribe(SUB_TOPIC, 1)
    for task in (up, down, messages):
        asyncio.create_task(task(client))
    n = 0
    while True:
        await asyncio.sleep(5)
        print("publish", n)
        # If Network is down the following will pause for the duration.
        await client.publish(PUB_TOPIC, f"{n} repubs: {client.REPUB_COUNT} outages: {outages}", qos=1)
        n += 1


# Define configuration
config["server"] = SERVER
config["will"] = (PUB_TOPIC, "Goodbye cruel world!", False, 0)
config["keepalive"] = 120
config["queue_len"] = 1  # Use event interface with default queue
config['clean'] = False
config['clean_init'] = False

# Bring up LAN
if not on_pc:
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
    client.close()  # Prevent LmacRxBlk:1 errors
    asyncio.new_event_loop()
