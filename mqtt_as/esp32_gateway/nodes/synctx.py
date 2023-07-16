# synctx.py A synchronous ESPNOW node

# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

'''
Illustrates a continuously running synchronous application which is resilient in
the presence of outages and channel changes.

To test need something like
mosquitto_sub -h 192.168.0.10 -t shed
mosquitto_pub -h 192.168.0.10 -t foo_topic -m "hello" -q 1
optionally:
mosquitto_sub -h 192.168.0.10 -t gw_errors
mosquitto_sub -h 192.168.0.10 -t gw_status
'''

import time, gc
from link import link 

def subs(topic, message, retained):  # Handle subscriptions
    print(f'Got subscription   topic: "{topic}" message: "{message}" retained {retained}')

link.subscribe("foo_topic", 1)
n = 0  # Message count
nr_count = 0  # Message failure count
while True:
    nfails = 0  # Attempt to reconnect after 5 consecutive failures
    gc.collect()
    while not link.publish("shed", f"Count {n} Response fails {nr_count} mem_free {gc.mem_free()}", qos=4, subs=subs):
        nr_count += 1  # Radio connectivity/Gateway/AP/broker is down.
        nfails += 1
        time.sleep(10)  # A real app might deeplsleep for a while
        if nfails > 5:  # There is a real outage, channel may have changed
            link.reconnect()
            nfails = 0  # Don't keep reconnecting frequently
    else:
        nfails = 0
        time.sleep(3)
    n += 1
