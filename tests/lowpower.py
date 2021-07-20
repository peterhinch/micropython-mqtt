# lowpower.py Test of asynchronous mqtt on Pyboard D under micopower operation
# (C) Copyright Peter Hinch 2019.
# Released under the MIT licence.

# red LED: ON == WiFi fail
# blue LED pulse == message received
# Publishes connection statistics.
import rtc_time_cfg
rtc_time_cfg.enabled = True

from mqtt_as import MQTTClient, config
from config import wifi_led, blue_led
import uasyncio as asyncio
 # Instantiate event loop with any args before running code that uses it
loop = asyncio.get_event_loop()

# **************
# Set up micropower operation. Note this is disabled if you have a USB
# connection as micropower would kill the USB link.
try:
    if asyncio.version[0] != 'fast_io':
        raise AttributeError
except:
    raise RuntimeError('This requires fast_io fork of uasyncio.')
import rtc_time
rtc_time.Latency(20)  # Define latency in ms
# **************

outages = 0

async def pulse():  # This demo pulses blue LED each time a subscribed msg arrives.
    blue_led(True)
    await asyncio.sleep(1)
    blue_led(False)

def sub_cb(topic, msg, retained):
    print((topic, msg, retained))
    loop.create_task(pulse())

async def wifi_han(state):
    global outages
    wifi_led(not state)  # Light LED when WiFi down
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
        await client.publish('result', '{} repubs: {} outages: {}'.format(n, client.REPUB_COUNT, outages), qos = 1)
        n += 1

# Define configuration
config['subs_cb'] = sub_cb
config['wifi_coro'] = wifi_han
config['will'] = ('result', 'Goodbye cruel world!', False, 0)
config['connect_coro'] = conn_han
config['keepalive'] = 120

# Set up client
print('Setting up client.')
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)
print('About to run.')
try:
    loop.run_until_complete(main(client))
finally:
    client.close()
