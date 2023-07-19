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

import time
import gc
from machine import Pin
from neopixel import NeoPixel
from link import gwlink 
import uasyncio as asyncio
from primitives import Delay_ms

black = (0, 0, 0)
red = (255, 0, 0)
green = (0, 255, 0)

async def do_subs(lk):
    lk.subscribe("foo_topic", 1)
    async for topic, message, retained in lk:
        print(f'Got subscription   topic: "{topic}" message: "{message}" retained {retained}')

async def flash(np, color):
    np[0] = color
    np.write()
    await asyncio.sleep_ms(500)
    np[0] = black
    np.write()

async def main(lk):
    np = NeoPixel(Pin(40), 1)
    asyncio.create_task(lk.run(1000))  # Latency in ms
    asyncio.create_task(do_subs(lk))
    #asyncio.create_task(pingtest(lk))
    lk_timeout = Delay_ms(lk.reconnect, duration = 30_000)  # .reconnect is blocking
    n = 0  # Message count
    nr_count = 0  # Message failure count
    while True:
        lk_timeout.trigger()
        gc.collect()
        while not lk.publish("shed", f"Count {n} Response fails {nr_count} mem_free {gc.mem_free()}", qos=1):
            nr_count += 1  # Radio connectivity/Gateway/AP/broker is down.
            asyncio.create_task(flash(np, red))
            await asyncio.sleep(10)
        else:
            await asyncio.sleep(3)
            asyncio.create_task(flash(np, green))
        n += 1

async def pingtest(lk):
    while True:
        print(lk.ping())  # TODO receiver contention
        await asyncio.sleep(5)

try:
    asyncio.run(main(gwlink))
finally:
    _ = asyncio.new_event_loop()
