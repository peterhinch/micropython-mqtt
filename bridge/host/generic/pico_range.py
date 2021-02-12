# pico_range.py TEST PROGRAM for Pyboard MQTT bridge with generic host (e.g. Pico)
# Intended for checking behaviour at the limit of WiFi range and to demonstrate
# the crash handler and other techniques e.g. time reporting.

# Author: Peter Hinch.
# Copyright Peter Hinch 2017-2021 Released under the MIT license.

# Host is assumed to have no LED's. Output is via console.
# From PC issue (for example)
# mosquitto_pub -h 192.168.0.10 -t green -m on
# mosquitto_sub -h 192.168.0.10 -t result

import uasyncio as asyncio
from pbmqtt import MQTTlink
import hw_pico as hardware  #  Pin definitions. Heartbeat on Pico LED.
import net_local
from utime import time, localtime

out_time = time()   # Time WiFi outages

qos = 1             # for test all messages have the same qos
reset_count = 0     # ESP8266 forced resets. Expect 1 at start.
gcount = 1          # Count since wifi up

def cbnet(state, objlink):
    global out_time, gcount
    if state:
        print('cbnet: WiFi UP')
        delta = time() - out_time
        objlink.publish('result', 'WiFi up: out time = {}s'.format(delta), 0, qos)
    else:
        print('cbnet: WiFi DOWN')
        out_time = time()
        gcount = 0

async def publish(mqtt_link, tim):
    global status_vals, gcount  # gcount is count since last outage
    count = 1  # Count since first up
    while True:
        await mqtt_link.publish('result', '{} {} {}'.format(gcount, count, reset_count), 0, qos)
        count += 1
        gcount += 1
        await asyncio.sleep(tim)


def cbgreen(command, text, retained):
    print('green subscription received cmd=', command, 'text = ', text, 'retained', retained)

def cbcrash(mqtt_link):
    print('ESP8266 crash')

async def report_time(mqtt_link):
    t = await mqtt_link.get_time()
    print('Time', localtime(t))  # When an API is available we might set the RTC here

# The user_start callback. See docs 2.3.5.
def start(mqtt_link):
    global reset_count
    print('ESP8266 (re)started')
    reset_count += 1

async def main():
    asyncio.create_task(mqtt_link.subscribe('green', qos, cbgreen))   # LED control qos 1
    asyncio.create_task(publish(mqtt_link, 10))
    asyncio.create_task(report_time(mqtt_link))
    while True:
        await asyncio.sleep(10)

MQTTlink.will('result', 'pico_range client died')
mqtt_link = MQTTlink(hardware.d, net_local.d, user_start=(start, ()),
                     wifi_handler=(cbnet, ()), crash_handler=(cbcrash, ()),
                     debug=True, verbose=True)
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
