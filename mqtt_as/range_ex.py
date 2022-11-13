# range_ex.py Test of asynchronous mqtt client with clean session False.
# Extended version publishes SSID
# (C) Copyright Peter Hinch 2017-2022.
# Released under the MIT licence.

# Now uses the event interface

# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers

# This demo is for wireless range tests. If OOR the red LED will light.
# In range the blue LED will pulse for each received message.
# Uses clean sessions to avoid backlog when OOR.

# red LED: ON == WiFi fail
# blue LED pulse == message received
# Publishes connection statistics.

from mqtt_as import MQTTClient, RP2
if RP2:
    from sys import implementation
from mqtt_local import wifi_led, blue_led, config
import uasyncio as asyncio
import network
import gc

TOPIC = 'shed'  # For demo publication and last will use same topic

outages = 0
rssi = -199  # Effectively zero signal in dB.

async def pulse():  # This demo pulses blue LED each time a subscribed msg arrives.
    blue_led(True)
    await asyncio.sleep(1)
    blue_led(False)

# The only way to measure RSSI is via scan(). Alas scan() blocks so the code
# causes the obvious uasyncio issues.
async def get_rssi():
    global rssi
    s = network.WLAN()
    ssid = config['ssid'].encode('UTF8')
    while True:
        try:
            rssi = [x[3] for x in s.scan() if x[0] == ssid][0]
        except IndexError:  # ssid not found.
            rssi = -199
        await asyncio.sleep(30)

async def messages(client):
    async for topic, msg, retained in client.queue:
        print(f'Topic: "{topic.decode()}" Message: "{msg.decode()}" Retained: {retained}')
        asyncio.create_task(pulse())

async def down(client):
    global outages
    while True:
        await client.down.wait()  # Pause until connectivity changes
        client.down.clear()
        wifi_led(False)
        outages += 1
        print('WiFi or broker is down.')

async def up(client):
    while True:
        await client.up.wait()
        client.up.clear()
        wifi_led(True)
        print('We are connected to broker.')
        await client.subscribe('foo_topic', 1)

async def main(client):
    try:
        await client.connect()
    except OSError:
        print('Connection failed.')
        return
    asyncio.create_task(up(client))
    asyncio.create_task(down(client))
    asyncio.create_task(messages(client))
    n = 0
    s = '{} repubs: {} outages: {} rssi: {}dB free: {}bytes discards: {}'
    while True:
        await asyncio.sleep(5)
        gc.collect()
        m = gc.mem_free()
        print('publish', n)
        # If WiFi is down the following will pause for the duration.
        await client.publish(TOPIC, s.format(n, client.REPUB_COUNT, outages, rssi, m, client.queue.discards), qos = 1)
        n += 1

# Define configuration
config['will'] = (TOPIC, 'Goodbye cruel world!', False, 0)
config['keepalive'] = 120
config["queue_len"] = 4  # Use event interface

# Set up client. Enable optional debug statements.
MQTTClient.DEBUG = True
client = MQTTClient(config)

# Currently (Apr 22) this task causes connection periodically to be dropped on Arduino Nano Connect
# It does work on Pico W
if not RP2 or 'Pico W' in implementation._machine:
    asyncio.create_task(get_rssi())
try:
    asyncio.run(main(client))
finally:  # Prevent LmacRxBlk:1 errors.
    client.close()
    blue_led(True)
    asyncio.new_event_loop()

