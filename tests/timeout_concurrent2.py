# Author: Kevin Köck
# Copyright Kevin Köck 2019 Released under the MIT license
# Created on 2019-11-05

__updated__ = "2019-11-05"
__version__ = "0.1"

try:
    from mqtt_as_timeout_concurrent2 import MQTTClient
except ImportError:
    from ..mqtt_as_timeout_concurrent2 import MQTTClient

import uasyncio as asyncio

loop = asyncio.get_event_loop(waitq_len=60, runq_len=60)


async def publish(val, t):
    print("Publishing", val, "timeout", t)
    res = await client.publish("foo_topic", val, qos=1, timeout=t)
    print("publish result for", val, ":", res)


def callback(topic, msg, retained):
    print((topic, msg, retained))


first = True


async def conn_han(client):
    global first
    if first:
        # await client.subscribe('foo_topic', 1)
        loop = asyncio.get_event_loop()
        loop.create_task(publish("payload {!s}".format(1), 1))
        loop.create_task(publish("payload {!s}".format(2), 2))
        loop.create_task(client.subscribe("testtopic{!s}".format(3), qos=1, timeout=5))
        loop.create_task(publish("payload {!s}".format(4), 4))
        loop.create_task(publish("payload {!s}".format(5), 5))
        loop.create_task(client.subscribe("testtopic{!s}".format(6), qos=1, timeout=5))
        first = False
        await asyncio.sleep(1)
        print("Closing connection")
        await client.disconnect()
        await asyncio.sleep(5)
        print("Publishing disconnected")
        loop.create_task(publish("payload {!s}".format(1), 1))
        loop.create_task(publish("payload {!s}".format(2), 2))
        loop.create_task(client.subscribe("testtopic{!s}".format(3), qos=1, timeout=5))
        loop.create_task(publish("payload {!s}".format(4), 4))
        loop.create_task(publish("payload {!s}".format(5), 5))
        loop.create_task(client.subscribe("testtopic{!s}".format(6), qos=1, timeout=5))
        await asyncio.sleep(10)
        print("Reconnecting after all timeouts")
        await client.connect()
        loop.create_task(publish("payload {!s}".format(8), 8))
        await asyncio.sleep(5)
        print("Test done")
        await client.disconnect()


import config
from ubinascii import hexlify
from machine import unique_id


async def wifi(state):
    print("WIFI state", state)


async def eliza(*_):  # e.g. via set_wifi_handler(coro): see test program
    await asyncio.sleep_ms(20)


config_dict = {
    'client_id':     hexlify(unique_id()),
    'server':        config.MQTT_HOST,
    'port':          config.MQTT_PORT,
    'user':          config.MQTT_USER,
    'password':      config.MQTT_PASSWORD,
    'keepalive':     60,
    'ping_interval': 0,
    'ssl':           False,
    'ssl_params':    {},
    'response_time': 10,
    'clean_init':    True,
    'clean':         True,
    'max_repubs':    4,
    'will':          None,
    'subs_cb':       lambda *_: None,
    'wifi_coro':     wifi,
    'connect_coro':  eliza,
    'ssid':          None,
    'wifi_pw':       None,
}
config_dict['connect_coro'] = conn_han
config_dict['subs_cb'] = callback

client = MQTTClient(**config_dict)
client.DEBUG = True


async def main(client):
    await client.connect()
    n = 0
    while True:
        await asyncio.sleep(5)


def test():
    try:
        loop.run_until_complete(main(client))
    finally:
        client.close()  # Prevent LmacRxBlk:1 errors
