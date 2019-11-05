# totest.py Test of publish timeouts
from mqtt_as import MQTTClient, config
from config import wifi_led, blue_led
import uasyncio as asyncio

TOPIC = 'shed'  # For demo publication and last will use same topic

loop = asyncio.get_event_loop()
outages = 0

async def pulse(led):
    led(True)
    await asyncio.sleep(1)
    led(False)

def sub_cb(topic, msg, retained):
    print((topic, msg))

async def wifi_han(state):
    global outages
    if state:
        print('We are connected to broker.')
    else:
        outages += 1
        print('WiFi or broker is down.')
    await asyncio.sleep(1)

async def conn_han(client):
    await client.subscribe('foo_topic', 1)

async def main(client):
    try:
        await client.connect()
    except OSError:
        print('Connection failed.')
        return
    n = 0
    while True:
        await asyncio.sleep(5)
        print('publish', n)
        # If WiFi is down the following will pause for the duration.
        if await client.publish(TOPIC, '{} repubs: {} outages: {}'.format(n, client.REPUB_COUNT, outages), qos = 1, timeout = 5):
            led = blue_led
        else:
            led = wifi_led
        await pulse(led)
        n += 1

# Define configuration
config['subs_cb'] = sub_cb
config['wifi_coro'] = wifi_han
config['will'] = (TOPIC, 'Goodbye cruel world!', False, 0)
config['connect_coro'] = conn_han
config['keepalive'] = 120

# Set up client. Enable optional debug statements.
MQTTClient.DEBUG = True
client = MQTTClient(config)

try:
    loop.run_until_complete(main(client))
finally:  # Prevent LmacRxBlk:1 errors.
    client.close()
