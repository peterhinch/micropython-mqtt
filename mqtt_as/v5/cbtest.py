# cbtest.py Test of asynchronous V5 mqtt client with clean session: callback interface.
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
# Subscription callback
def sub_cb(topic, msg, retained, properties):
    print(f'Topic: "{topic.decode()}" Message: "{msg.decode()}" Retained: {retained}')
    if properties is None:
        print("Message has no properties.")
    else:
        print("Message properties:")
        for key in properties:
            print(f"{decode(key)} : {properties[key]}")


async def wifi_han(state):
    global outages
    print("Wifi is ", "up" if state else "down")
    if not state:
        outages += 1
    await asyncio.sleep(1)


# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    print("We are connected to broker.")
    await client.subscribe("foo_topic", 1)


async def main(client, props):
    try:
        await client.connect(quick=True)
    except OSError:
        print("Connection failed.")
        return
    await asyncio.sleep(1)
    print(f"Topic alias max {client.topic_alias_maximum}")
    n = 0
    s = "{} repubs: {} outages: {} free: {}"
    while True:
        await asyncio.sleep(5)
        print("publish", n)
        gc.collect()
        m = gc.mem_free()
        msg = s.format(n, client.REPUB_COUNT, outages, m)
        # If WiFi is down the following will pause for the duration.
        await client.publish(TOPIC, msg, qos=1, properties=props)
        n += 1


# Define configuration
config["will"] = (TOPIC, "Goodbye cruel world!", False, 0)
config["keepalive"] = 120
config["subs_cb"] = sub_cb
config["wifi_coro"] = wifi_han
config["connect_coro"] = conn_han
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
