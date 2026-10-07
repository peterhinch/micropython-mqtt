# pc_tls.py Test of TLS on the Unix build of MicroPython.
# Does not work under CPython.

# (C) Copyright Peter Hinch 2017-2026.
# Released under the MIT licence.

# This demo publishes to topic "result" and also subscribes to that topic.
# This demonstrates bidirectional TLS communication.
# You can also run the following on a PC to verify:
# mosquitto_sub -h test.mosquitto.org -t result
# To get mosquitto_sub to use a secure connection use this, offered by @gmrza:
# mosquitto_sub -h <my local mosquitto server> -t result -u <username> -P <password> -p 8883

# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers


from mqtt_as_eth import MQTTClient, config
import asyncio

SERVER = "test.mosquitto.org"


def sub_cb(topic, msg, retained):
    c, r = [int(x) for x in msg.decode().split(" ")]
    print(
        "Topic = {} Count = {} Retransmissions = {} Retained = {}".format(
            topic.decode(), c, r, retained
        )
    )


async def net_han(state):
    print("Broker is ", "up" if state else "down")
    await asyncio.sleep(1)


# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    await client.subscribe("result", 1)


async def main(client):
    await client.connect()
    n = 0
    await asyncio.sleep(2)  # Give broker time
    while True:
        print("publish", n)
        # If broker is down the following will pause for the duration.
        await client.publish("result", "{} {}".format(n, client.REPUB_COUNT), qos=1)
        n += 1
        await asyncio.sleep(20)  # Broker is slow


# Define configuration
config["subs_cb"] = sub_cb
config["server"] = SERVER
config["connect_coro"] = conn_han
config["wifi_coro"] = net_han
config["ssl"] = True

# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)
try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()
