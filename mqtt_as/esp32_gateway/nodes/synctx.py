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

import time
import gc
import sys
from .link import Link, PUB_OK, BROKER_OUT, ESP_FAIL, PUB_FAIL
from .link_setup import gateway, channel, credentials  # Common args
try:
    gwlink = Link(gateway, channel, credentials)
except OSError:
    print(f"Failed to connect to {gateway}.")
    sys.exit(0)

def subs(topic, message, retained):  # Handle subscriptions
    print(f'Got subscription   topic: "{topic}" message: "{message}" retained {retained}')

gwlink.subscribe("foo_topic", 1)
n = 0  # Message count
nr_count = 0  # Message failure count
br_count = 0  # Broker fail count
print("Actual channel", gwlink.get_channel())  # Demo means of querying channel of gateway
while True:
    gc.collect()
    while gwlink.ping() != PUB_OK:
        time.sleep(1)  # Wait for connectivity
    args = ("shed", f"Count {n} ESPNow fails {nr_count} Broker fails {br_count} mem_free {gc.mem_free()}", False, 1)
    if (res := gwlink.publish(*args)) == PUB_OK:
        gwlink.get(subs)
        n += 1
    elif res == ESP_FAIL:  # ESPNow problem
        nr_count += 1
    elif res == BROKER_OUT:  # Pub queue is filling
        br_count += 1
    time.sleep(3)

# No missed messages on broker out, but get dupes and queueing.
# While WiFi out, miss incoming subs.
