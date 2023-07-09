# synctx.py A synchronous ESPNOW node

# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

'''
To test need something like
mosquitto_sub -h 192.168.0.10 -t shed
mosquitto_pub -h 192.168.0.10 -t foo_topic -m "hello" -q 1
optionally:
mosquitto_sub -h 192.168.0.10 -t gw_errors
mosquitto_sub -h 192.168.0.10 -t gw_status
'''

import json
import time
from machine import deepsleep
from common import gateway, sta, espnow, subscribe

def subs(message):  # Handle subscriptions
    print(f'Got subscription   topic: "{message[0]}" message: "{message[1]}" retained {message[2]}')

fail_count = 0

def publish(espnow, topic, msg, retain=False, qos=0):
    global fail_count
    message = json.dumps([topic, msg, retain, qos])
    got_ack = False
    while not got_ack:  # Repeat pubs until an ACK is received
        try:
            if not espnow.send(gateway, message):
                return False
            else:
                while True:
                    mac, msg = espnow.recv(200)
                    if mac is None:  # Timeout: no pending message from gateway
                        if not got_ack:
                            fail_count += 1
                        break
                    message = json.loads(msg)
                    topic = message[0]
                    if topic == "ACK":
                        got_ack = True
                    elif topic == "OUT":  # WiFi/broker fail
                        return False
                    else:
                        subs(message)  # Process a subscription
        except OSError as e:  # Radio communications with gateway down.
            fail_count += 1
            time.sleep_ms(100)  # Try again after short break?
    return True  # Pub succeeded

subscribe("foo_topic", 1)

n = 0
nr_count = 0
while True:
    while not publish(espnow, "shed", f"Count {n} Ack fails {fail_count} Response fails {nr_count}", qos=4):  # 0, 1, 4 or 5
        nr_count += 1  # Gateway/AP/broker is down.
        time.sleep(5)  # A real app would deeplsleep for a while
        # TODO may need to scan for channels if outage persists
    else:
        time.sleep(3)
    n += 1
