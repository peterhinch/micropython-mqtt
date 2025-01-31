# tests/v3/test.py V3 protocol test. Challenges device running tests/v3/target.py
# Should also pass when run against tests/v5/target.py

# (C) Copyright Peter Hinch 2025.
# Released under the MIT licence.

# Run with
# mpremote mount . exec "import mqtt_as.tests.v3.test"


from mqtt_as import MQTTClient
from mqtt_local import wifi_led, blue_led, config
import asyncio
import gc
import json
from primitives import RingbufQueue

expect = RingbufQueue(10)  # Expected incoming messages
arrive = asyncio.Event()  # Message has arrived
match = False  # Does incoming message match expected?

FAIL = "\x1b[93mFAIL\x1b[39m"
PASS = "\x1b[92mPASS\x1b[39m"


async def pulse():  # This demo pulses blue LED each time a subscribed msg arrives.
    blue_led(True)
    await asyncio.sleep(1)
    blue_led(False)


# Incoming messages
async def messages():
    global match
    async for topic, msg, retained in client.queue:
        asyncio.create_task(pulse())
        topic = topic.decode()
        msg = msg.decode()
        # print(f'Topic: "{topic}" Message: "{msg}" Retained: {retained}')
        if topic == "response":  # msg is json encoded topic and message of received pub
            q = json.loads(msg)
            topic, msg = q[:2]  # Ignore properties encoded by V5 target

        etopic, emsg = await expect.get()  # Expected topic and message
        match = topic == etopic and msg == emsg
        arrive.set()


# Return True if expected response is received within a time period.
async def any_response(t=3):
    res = False  # Assume failure
    await asyncio.sleep(1)
    try:
        if await asyncio.wait_for(arrive.wait(), t):  # We have a messge
            if not (res := match):
                print("Message mismatch")
    except asyncio.TimeoutError:  # No response received
        pass
    return res


# Send a command to the remote
async def command(cmd, topic, msg=""):
    await client.publish("control", json.dumps([cmd, topic, msg]))


# Reset queue and Event prior to a test
def init(expected=None):
    while expect.qsize():  # Clear queue
        expect.get_nowait()
    if expected is not None:  # Push expected data
        expect.put_nowait(expected)
    arrive.clear()


# Subscribe to passed topic. Ask remote to publish to it. Check response.
async def request_pub(topic, msg):
    init([topic, msg])
    await client.subscribe(topic, 1)
    await asyncio.sleep(1)
    # Request publication
    await command("publish", topic, msg)
    res = await any_response(3)  # Await incoming message
    await client.unsubscribe(topic)  # Tidy up local client.
    return res


# Ask remote to subscribe to a topic. Publish to it. Check remote's response.
async def request_sub(topic, msg):
    init([topic, msg])
    # Tell target to subscribe to topic
    await command("subscribe", topic)
    await asyncio.sleep(1)
    # Test subscription by publishing message to it
    await client.publish(topic, msg)
    # Wait for target's response. This is to topic "response" with json-encoded
    # topic and message.
    return await any_response(3)


# Ask remote to unsubscribe from a topic. Publish to it. Check for no response.
async def request_unsub(topic, msg):
    init([topic, msg])  # Prepare for failure to unsubscribe
    # Tell target to unsubscribe to topic
    await command("unsubscribe", topic)
    await asyncio.sleep(1)
    # Test unsubscription by publishing message to it
    await client.publish(topic, msg)
    # Wait for target's response: should time out
    return await any_response(3)


async def run_tests():
    await client.up.wait()  # Ensure client is ready
    client.up.clear()
    wifi_led(True)
    print("Connected to broker.")
    await asyncio.sleep(1)
    await client.subscribe("response", 1)
    print()
    print("Remote publication test.")
    r = await request_pub("foo topic", "hello")
    print(f"Publish test {PASS if r else FAIL}\n")

    # Request subscription and test by sending it a message
    print("Remote subscription test.")
    topic = "target test topic"
    msg = "this is a message"
    r = await request_sub(topic, msg)
    print(f"Subscribe test {PASS if r else FAIL}\n")

    print("Remote unsubscribe test - please wait.")
    # Request unsubscription. Should fail to respond to challenge publication
    r = await request_unsub(topic, msg)
    print(f"Unsubscribe test {FAIL if r else PASS}\n")

    print("Remote publication test - long topic and message.")
    topic = "abcdefghij" * 20  # 200 characters
    msg = "zyxwvutsrq" * 20
    r = await request_pub(topic, msg)
    print(f"Publish test {PASS if r else FAIL}\n")

    print("Remote subscription test - long topic and message.")
    r = await request_sub(topic, msg)
    print(f"Subscribe test {PASS if r else FAIL}\n")

    print("Remote unsubscribe test - long topic and message.")
    # Request unsubscription. Should fail to respond to challenge publication
    r = await request_unsub(topic, msg)
    print(f"Unsubscribe test {FAIL if r else PASS}\n")

    print("Remote unsubscribe test - target not subscribed to topic.")
    # Request unsubscription. Should fail to respond to challenge publication
    r = await request_unsub("rats", "nonsense")
    print(f"Unsubscribe test {FAIL if r else PASS}\n")

    print("Repeat publication test to ensure target running OK.")
    r = await request_pub("foo topic", "hello")
    print(f"Publish test {PASS if r else FAIL}\n")


async def main():
    try:
        await client.connect(quick=True)
    except OSError:
        print("Connection failed.")
        return
    asyncio.create_task(messages())  # Handle incoming
    await run_tests()


# Define configuration
config["keepalive"] = 120
config["queue_len"] = 4  # Use event interface

# Set up client. Enable optional debug statements.
# MQTTClient.DEBUG = True
client = MQTTClient(config)

try:
    asyncio.run(main())
finally:
    client.close()
    blue_led(True)
    asyncio.new_event_loop()
