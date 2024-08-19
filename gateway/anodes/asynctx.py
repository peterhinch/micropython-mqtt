# asynctx.py An asynchronous ESPNOW node

# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

'''
Illustrates a continuously running asynchronous application which is resilient in
the presence of outages and channel changes.

To test need something like
mosquitto_sub -h 192.168.0.10 -t shed
mosquitto_pub -h 192.168.0.10 -t foo_topic -m "hello" -q 1
optionally:
mosquitto_sub -h 192.168.0.10 -t gw_errors
mosquitto_sub -h 192.168.0.10 -t gw_status
'''

import gc
from machine import Pin
from neopixel import NeoPixel
import uasyncio as asyncio
from .primitives import Delay_ms
from .alink import ALink
# Convenience file for distributing common constructor args to multiple nodes
from .link_setup import gateway, channel, credentials, debug, poll_interval
gwlink = ALink(gateway, channel, credentials, debug, poll_interval)  # From link_setup.py

black = (0, 0, 0)
red = (255, 0, 0)
green = (0, 255, 0)
blue = (0, 0, 255)

async def do_subs(lk):
    await lk.subscribe("foo_topic", 1)
    async for topic, message, retained in lk:
        print(f'Got subscription   topic: "{topic}" message: "{message}" retained {retained}')

async def flash(np, color):
    np[0] = color
    np.write()
    await asyncio.sleep_ms(500)
    np[0] = black
    np.write()

async def broker(lk, np):
    while True:
        print("Waiting for down")
        lk.broker_up.clear()
        lk.broker_down.clear()
        await lk.broker_down.wait()
        print("Got down")
        lk.broker_up.clear()
        lk.broker_down.clear()
        np[0] = blue
        np.write
        await lk.broker_up.wait()
        print("Got up")
        np[0] = black
        np.write

# Publish blocks indefinitely on outage. Reconnect to WiFi to enable ESPNOW if it takes too long.
async def main(lk):
    np = NeoPixel(Pin(40), 1)
    asyncio.create_task(lk.run())
    asyncio.create_task(do_subs(lk))
    asyncio.create_task(broker(lk, np))
    lk_timeout = Delay_ms(lk.reconnect, duration = 30_000)
    n = 0  # Message count
    nr_count = 0  # Message failure count
    while True:
        lk_timeout.trigger()
        gc.collect()
        await lk.publish("shed", f"Count {n} Response fails {nr_count} mem_free {gc.mem_free()}", qos=1)
        await asyncio.sleep(3)
        asyncio.create_task(flash(np, green))
        n += 1


try:
    asyncio.run(main(gwlink))
finally:
    gwlink.close()  # Leave hardware in a good state.
    _ = asyncio.new_event_loop()
