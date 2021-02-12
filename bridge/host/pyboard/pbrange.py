# pbrange.py TEST PROGRAM for Pyboard MQTT link
# Intended for checking behaviour at the limit of WiFi range and to demonstrate
# the crash handler and other techniques e.g. time reporting.

# Author: Peter Hinch.
# Copyright Peter Hinch 2017-2021 Released under the MIT license.

# From PC issue (for example)
# mosquitto_pub -h 192.168.0.10 -t green -m on
# mosquitto_sub -h 192.168.0.10 -t result

import pyb
import uasyncio as asyncio
from pbmqtt import MQTTlink
import hardware
import net_local
from utime import time, localtime

out_time = time()   # Time WiFi outages
                    # red led is used for heartbeat by pbmqtt.py
green = pyb.LED(2)  # Pulse on any msg addressed to green
amber = pyb.LED(3)  # On if WiFi up
blue = pyb.LED(4)   # Pulse on ESP8266 reboot
qos = 1             # for test all messages have the same qos
reset_count = 0     # ESP8266 forced resets. Expect 1 at start.
status_vals = []    # Unhandled status numbers
gcount = 1          # Count since wifi up

def cbnet(state, objlink):
    global out_time, gcount
    if state:
        amber.on()
        delta = time() - out_time
        objlink.publish('result', 'WiFi up: out time = {}s'.format(delta), 0, qos)
    else:
        amber.off()
        out_time = time()
        gcount = 0

async def publish(mqtt_link, tim):
    global status_vals, gcount  # gcount is count since last outage
    count = 1  # Count since first up
    while True:
        await mqtt_link.publish('result', '{} {} {}'.format(gcount, count, reset_count), 0, qos)
        count += 1
        gcount += 1
        if status_vals:
            msg = 'status: {}'.format(repr(status_vals))
            await mqtt_link.publish('result', msg, 0, qos)
            status_vals = []
        await asyncio.sleep(tim)

async def pulse(led, ms=3000):
    led.on()
    await asyncio.sleep_ms(ms)
    led.off()

def cbgreen(command, text, retained):
    asyncio.create_task(pulse(green, 500))

def cbcrash(mqtt_link):
    print('ESP8266 crash')

async def set_rtc(mqtt_link, local_time_offset):
    t = await mqtt_link.get_time()
    t += local_time_offset * 3600
    rtc = pyb.RTC()
    tm = localtime(t)
    print('RTC set. Time:', tm)
    tm = tm[0:3] + (tm[6] + 1,) + tm[3:6] + (0,)
    rtc.datetime(tm)
    rtc_set = True

# The user_start callback. See docs 2.3.5.
def start(mqtt_link):
    global reset_count
    asyncio.create_task(pulse(blue))  # Flash blue LED each time we restart ESP8266
    reset_count += 1

async def main():
    asyncio.create_task(mqtt_link.subscribe('green', qos, cbgreen))  # LED control qos 1
    asyncio.create_task(publish(mqtt_link, 10))
    asyncio.create_task(set_rtc(mqtt_link, 0))
    while True:
        await asyncio.sleep(10)

MQTTlink.will('result', 'client died')
mqtt_link = MQTTlink(hardware.d, net_local.d, user_start=(start, ()),
                     wifi_handler=(cbnet, ()), crash_handler=(cbcrash, ()),
                     debug=True, verbose=True)
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
