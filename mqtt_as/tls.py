# tls.py Test of asynchronous mqtt client with SSL for Pyboard D. Tested OK.

# (C) Copyright Peter Hinch 2017-2019.
# Released under the MIT licence.

# This demo publishes to topic "result" and also subscribes to that topic.
# This demonstrates bidirectional TLS communication.
# You can also run the following on a PC to verify:
# mosquitto_sub -h test.mosquitto.org -t result
# I haven't yet figured out how to get mosquitto_sub to use a secure connection.

# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers

# red LED: ON == WiFi fail
# green LED heartbeat: demonstrates scheduler is running.

from mqtt_as import MQTTClient
from mqtt_local import config
import uasyncio as asyncio
from pyb import LED

SERVER = 'test.mosquitto.org'

loop = asyncio.get_event_loop()

# Subscription callback
async def flash():
    LED(3).on()
    await asyncio.sleep_ms(500)
    LED(3).off()

sub_led = LED(3)  # Blue
def sub_cb(topic, msg, retained):
    c, r = [int(x) for x in msg.decode().split(' ')]
    print('Topic = {} Count = {} Retransmissions = {} Retained = {}'.format(topic.decode(), c, r, retained))
    loop.create_task(flash())

# Demonstrate scheduler is operational and TLS is nonblocking.
async def heartbeat():
    led = LED(2)  # Green
    while True:
        await asyncio.sleep_ms(500)
        led.toggle()

wifi_led = LED(1)  # LED on for WiFi fail/not ready yet

async def wifi_han(state):
    if state:
        wifi_led.off()
    else:
        wifi_led.on()
    print('Wifi is ', 'up' if state else 'down')
    await asyncio.sleep(1)

# If you connect with clean_session True, must re-subscribe (MQTT spec 3.1.2.4)
async def conn_han(client):
    await client.subscribe('result', 1)

async def main(client):
    await client.connect()
    n = 0
    await asyncio.sleep(2)  # Give broker time
    while True:
        print('publish', n)
        # If WiFi is down the following will pause for the duration.
        await client.publish('result', '{} {}'.format(n, client.REPUB_COUNT), qos = 1)
        n += 1
        await asyncio.sleep(20)  # Broker is slow

# Define configuration
config['subs_cb'] = sub_cb
config['server'] = SERVER
config['connect_coro'] = conn_han
config['wifi_coro'] = wifi_han
config['ssl'] = True

# Set up client
MQTTClient.DEBUG = True  # Optional
client = MQTTClient(config)

loop.create_task(heartbeat())
try:
    loop.run_until_complete(main(client))
finally:
    client.close()
