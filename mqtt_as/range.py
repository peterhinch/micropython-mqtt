# clean.py Test of asynchronous mqtt client with clean session False.
# (C) Copyright Peter Hinch 2017.
# Released under the MIT licence.

# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers

# This demo is for wireless range tests. If OOR the red LED will light.
# In range the blue LED will pulse for each received message.
# Uses clean sessions to avoid backlog when OOR.

# red LED: ON == WiFi fail
# blue LED pulse == message received
# Publishes connection statistics.

from mqtt_as import MQTTClient, config
from config import config
import uasyncio as asyncio
from machine import Pin

SERVER = '192.168.0.9'  # Change to suit e.g. 'iot.eclipse.org'

wifi_led = Pin(0, Pin.OUT, value = 0)  # Red LED for WiFi fail/not ready yet
blue_led = Pin(2, Pin.OUT, value = 1)  # Message received

loop = asyncio.get_event_loop()

outages = 0

async def pulse():  # This demo pulses blue LED each time a subscribed msg arrives.
    blue_led(False)
    await asyncio.sleep(1)
    blue_led(True)

def sub_cb(topic, msg):
    print((topic, msg))
    loop.create_task(pulse())

async def wifi_han(state):
    global outages
    wifi_led(state)  # Off == WiFi down (LED is active low)
    if state:
        print('We are connected to broker.')
    else:
        outages += 1
        print('WiFi or broker is down.')
    await asyncio.sleep(1)

async def conn_han(client):
    await client.subscribe('foo_topic', 1)

async def main(client):
    await client.connect()
    n = 0
    while True:
        await asyncio.sleep(5)
        print('publish', n)
        # If WiFi is down the following will pause for the duration.
        await client.publish('result', '{} repubs: {} outages: {}'.format(n, client.REPUB_COUNT, outages), qos = 1)
        n += 1

# Define configuration
config['subs_cb'] = sub_cb
config['wifi_coro'] = wifi_han
config['will'] = ('result', 'Goodbye cruel world!', False, 0)
config['connect_coro'] = conn_han
config['server'] = SERVER
config['keepalive'] = 120

# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)

try:
    loop.run_until_complete(main(client))
finally:  # Prevent LmacRxBlk:1 errors.
    client.close()
