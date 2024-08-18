# basic.py Test of asynchronous V5 mqtt client with clean session.
# Simple demo of MQTTv5 properties

# (C) Copyright Peter Hinch 2024.
# Released under the MIT licence.

# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers

# Publishes connection statistics.
# To create a publication which will be receive by this test:
# mosquitto_pub -h 192.168.0.10 -t foo_topic -m "hello hello" -D PUBLISH user-property foo bar  -V 5
# To verify above publicatin:
# mosquitto_sub -h 192.168.0.10 -t foo_topic  -V 5 -F "Properties %P payload %p"
# To verify publications by this program:
# mosquitto_sub -h 192.168.0.10 -t shed  -V 5 -F "Properties %P payload %p"


from mqtt_as import MQTTClient, RP2

from mqtt_local import config  # Sets "server", "ssid", "wifi_pw"
import asyncio
import gc

TOPIC = "shed"  # For demo publication and last will use same topic

outages = 0


def decode(key):
    names = {
        0x01: "Payload Format Indicator",
        0x02: "Message Expiry Interval",
        0x03: "Content Type",
        0x08: "Response Topic",
        0x09: "Correlation Data",
        0x0B: "Subscription Identifier",
        0x23: "Topic alias",
        0x26: "User Property",
    }
    if key in names:
        return names[key]
    return f"Unknown: {key}"


# Incoming properties comprise a dict with one key for each property in the message
async def messages(client):
    async for topic, msg, retained, properties in client.queue:
        print(f'Topic: "{topic.decode()}" Message: "{msg.decode()}" Retained: {retained}')
        if properties is None:
            print("Message has no properties.")
        else:
            print("Message properties:")
            for key in properties:
                print(f"{decode(key)} : {properties[key]}")


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


async def main(client, props):
    try:
        await client.connect(quick=True)
    except OSError:
        print("Connection failed.")
        return
    asyncio.create_task(up(client))
    asyncio.create_task(down(client))
    asyncio.create_task(messages(client))
    await asyncio.sleep(1)
    print(f"Topic alias max {client.topic_alias_maximum}")
    n = 0
    s = "{} repubs: {} outages: {} free: {}bytes discards: {}"
    while True:
        await asyncio.sleep(5)
        print("publish", n)
        gc.collect()
        m = gc.mem_free()
        msg = s.format(n, client.REPUB_COUNT, outages, m, client.queue.discards)
        # If WiFi is down the following will pause for the duration.
        await client.publish(TOPIC, msg, qos=1, properties=props)
        n += 1


# Define configuration
config["will"] = (TOPIC, "Goodbye cruel world!", False, 0)
config["keepalive"] = 120
config["queue_len"] = 4  # Use event interface
config["mqttv5"] = True
config["mqttv5_con_props"] = {
    0x11: 3600,
}  # Session Expiry Interval

# Set up client. Enable optional debug statements.
MQTTClient.DEBUG = True
client = MQTTClient(config)
# Properties for publication
pub_props = {
    0x26: {"value": "test"},  # User Property (UTF-8 string pair)
    0x09: b"correlation_data",  # Correlation Data (binary)
    0x08: "response_topic",  # Response Topic (UTF-8 string)
    0x02: 60,  # Message Expiry Interval (integer)
}

try:
    asyncio.run(main(client, pub_props))
finally:
    client.close()
    asyncio.new_event_loop()
