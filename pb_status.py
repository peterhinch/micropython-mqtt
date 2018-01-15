# pb_status.py TEST PROGRAM for Pyboard MQTT link
# Demonstrates the interception of status messages.

# Author: Peter Hinch.
# Copyright Peter Hinch 2017-2018 Released under the MIT license.

# From PC issue (for example)
# mosquitto_pub -h 192.168.0.9 -t green -m on
# mosquitto_sub -h 192.168.0.9 -t result

import pyb
import uasyncio as asyncio
import asyn
from pbmqtt import MQTTlink, default_status_handler
from net_local import init  # Local network, broker and pin details
from status_values import *  # Because we're intercepting status.
from utime import time

out_time = time()   # Time WiFi outages
                    # red led is used for heartbeat by pbmqtt.py
green = pyb.LED(2)  # Pulse on any msg addressed to green
amber = pyb.LED(3)  # On if WiFi up
blue = pyb.LED(4)   # Pulse on ESP8266 reboot
qos = 1             # for test all messages have the same qos
reset_count = 0     # ESP8266 forced resets. Expect 1 at start.
status_vals = []    # Unhandled status numbers
gcount = 1          # Count since power up

async def status_handler(mqtt_link, status):
    global out_time
    res = await default_status_handler(mqtt_link, status)
    if res is not None:  # Handle failure on initialisation
        # res == 1 occurs on 1st run only. Tells driver to try the network
        # specified in net_local.
        # res == 0 indicates failure to connect. The default handler waits 30 secs
        # before returning 0 to give time for the network to come up.
        # If we return 0 the ESP8266 will be rebooted
        return res
    # WiFi handling for demo: easier to use wifi_handler (see pb_simple.py)
    if status == WIFI_UP:
        amber.on()
        delta = time() - out_time
        mqtt_link.publish('result', 'WiFi up: out time = {}s'.format(delta), 0, qos)
        return
    if status == WIFI_DOWN:
        out_time = time()
        amber.off()
        return
    if status == PUBOK:
        return
    status_vals.append(status)  # We will publish non-routine values

@asyn.cancellable
async def publish(mqtt_link, tim):
    global status_vals, gcount
    count = 1  # Count since last ESP8266 reboot
    while True:
        mqtt_link.publish('result', '{} {} {}'.format(gcount, count, reset_count), 0, qos)
        count += 1
        gcount += 1
        if status_vals:
            msg = 'status: {}'.format(repr(status_vals))
            mqtt_link.publish('result', msg, 0, qos)
            status_vals = []
        await asyn.sleep(tim)

async def pulse(led, ms=3000):
    led.on()
    await asyncio.sleep_ms(ms)
    led.off()

def cbgreen(command, text):
    loop = asyncio.get_event_loop()
    loop.create_task(pulse(green, 500))

# The user_start callback. See docs 2.3.5.
def start(mqtt_link):
    global reset_count
    mqtt_link.subscribe('green', qos, cbgreen)    # LED control qos 1
    loop = asyncio.get_event_loop()
    loop.create_task(asyn.Cancellable(publish, mqtt_link, 10)()) # Publish a count every 10 seconds
    loop.create_task(pulse(blue))  # Flash blue LED each time we restart ESP8266
    reset_count += 1

MQTTlink.will('result', 'client died')
init['user_start'] = start

mqtt_link = MQTTlink(init)
mqtt_link.status_handler(status_handler)  # Override the default
loop = asyncio.get_event_loop()
loop.run_forever()
