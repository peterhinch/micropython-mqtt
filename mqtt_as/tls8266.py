# tls8266.py Test of asynchronous mqtt client with SSL. Doesn't actually work:
# fails on connect with ssl_handshake_status: -4
# Please help me fix it...

# (C) Copyright Peter Hinch 2017-2019.
# Released under the MIT licence.

# This demo publishes to topic "result" and also subscribes to that topic.
# This demonstrates bidirectional TLS communication.
# You can also run the following on a PC to verify:
# mosquitto_sub -h test.mosquitto.org -t result

# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers

# red LED: ON == WiFi fail
# blue LED heartbeat: demonstrates scheduler is running.

from mqtt_as import MQTTClient
from config import config
import uasyncio as asyncio
from machine import Pin, unique_id

SERVER = 'test.mosquitto.org'

# Subscription callback
def sub_cb(topic, msg, retained):
    print((topic, msg, retained))

# Demonstrate scheduler is operational.
async def heartbeat():
    led = Pin(2, Pin.OUT)
    while True:
        await asyncio.sleep_ms(500)
        led(not led())

wifi_led = Pin(0, Pin.OUT, value=0)  # LED on for WiFi fail/not ready yet

async def wifi_han(state):
    wifi_led(state)
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    await client.subscribe('result', 1)

async def main(client):
    await client.connect()
    n = 0
    while True:
        await asyncio.sleep(20)  # Broker is slow
        print('publish', n)
        # If WiFi is down the following will pause for the duration.
        await client.publish('result', '{} {}'.format(n, client.REPUB_COUNT), qos = 1)
        n += 1

# Define configuration
config['subs_cb'] = sub_cb
config['server'] = SERVER
config['connect_coro'] = conn_han
config['wifi_coro'] = wifi_han
config['ssl'] = True

# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)

loop = asyncio.get_event_loop()
loop.create_task(heartbeat())
try:
    loop.run_until_complete(main(client))
finally:
    client.close()  # Prevent LmacRxBlk:1 errors
