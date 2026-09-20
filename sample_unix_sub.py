#!/usr/bin/env micropython
# (C) Copyright Peter Hinch 2017-2024.
# (C) Copyright Marcos Diez 2016.
# Released under the MIT licence.

# sample_unix_pub.py connects to an MQTT server and publishes messages.
# sample_unix_sub.py connects to an MQTT server and receives  messages.

# These were tested on micropython on linux (amd64)


# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers

from mqtt_as import MQTTClient


config = {
	"server": "192.168.58.176",  # THIS IS PROBABLY WHAT YOU WANT TO CHANGE FIRST
    "queue_len": 10,
    "client_id": "linux_sub",
    "user": "config_user",
    "password": "config_password",
    "keepalive": 10,
    "response_time": 10,
    "max_repubs": 10,
    "clean_init": True, # clean_session state on first connection
    "clean": False, # clean_session state on reconnect
    "will": None,

    "ssid": "my_wifi",
    "wifi_pw": "wifi_pwd",
    "ssl": False,
    "ssl_params": None,
    "ping_interval": 10,


    "wifi_coro": "wifi_coro",
    "connect_coro": "connect_coro",

    "subs_cb": "test/helloworld",

    "topic_sub": "test/helloworld",
    "topic_pub": "test/helloworld",
    "qos": 1,

    "port": 1883,
    "gateway": None,

}

import uasyncio as asyncio

outages = 0


async def pulse():  # This demo pulses blue LED each time a subscribed msg arrives.
    await asyncio.sleep(1)


async def messages(client):
    async for topic, msg, retained in client.queue:
        print(f'Topic: "{topic.decode()}" Message: "{msg.decode()}" Retained: {retained}')
        asyncio.create_task(pulse())


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
        print(f'Subscribing to topic {config["topic_sub"]} with QOS={config["qos"]}.')
        await client.subscribe( config["topic_sub"] , config["qos"])


async def main(client):
    try:
        await client.connect(quick=True)
    except OSError:
        print("Connection failed.")
        return
    for task in (up, down, messages):
        asyncio.create_task(task(client))
    # n = 0
    while True:
        await asyncio.sleep(5)
        # msg =  "{} repubs: {} outages: {}".format(n, client.REPUB_COUNT, outages)
        # print(f"Publishing to topic {config['topic_pub']}: {msg}")
        # # If WiFi is down the following will pause for the duration.
        # await client.publish(config["topic_pub"], msg, qos=config["qos"])
        # n += 1


# Define configuration
config["will"] = (config["topic_pub"], "Goodbye cruel world!", False, 0)
config["keepalive"] = 120
config["queue_len"] = 1  # Use event interface with default queue

# Set up client. Enable optional debug statements.
MQTTClient.DEBUG = True
client = MQTTClient(config)

try:
    asyncio.run(main(client))
finally:  # Prevent LmacRxBlk:1 errors.
    client.close()
    asyncio.new_event_loop()
