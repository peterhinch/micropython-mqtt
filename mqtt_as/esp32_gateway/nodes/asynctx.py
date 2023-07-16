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
from link import link 
import usayncio as asyncio
from primitives import Delay_ms

async def do_subs():
    link.subscribe("foo_topic", 1)
    async for topic, message, retained in link:
        print(f'Got subscription   topic: "{topic}" message: "{message}" retained {retained}')

async def main():
    asyncio.create_task(do_subs())
    link_timeout = Delay_ms(link.reconnect, duration = 30_000)  # .reconnect is blocking
    n = 0  # Message count
    nr_count = 0  # Message failure count
    while True:
        link_timeout.trigger()
        gc.collect()
        while not link.publish("shed", f"Count {n} Response fails {nr_count} mem_free {gc.mem_free()}", qos=4):
            nr_count += 1  # Radio connectivity/Gateway/AP/broker is down.
            await asyncio.sleep(10)
        else:
            await asyncio.sleep(3)
        n += 1

try:
    asyncio.run(main())
finally:
    _ asyncio.new_event_loop()
