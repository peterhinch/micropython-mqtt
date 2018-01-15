# pbmqtt_test.py TEST PROGRAM for Pyboard MQTT link
# This tests the ramcheck facility.

# Author: Peter Hinch.
# Copyright Peter Hinch 2017 Released under the MIT license.

# From PC issue (for example)
# mosquitto_pub -h 192.168.0.9 -t green -m on
# mosquitto_sub -h 192.168.0.9 -t result

from machine import Pin, Signal
import pyb
import uasyncio as asyncio
import asyn
from pbmqtt import MQTTlink
from net_local import init  # Local network, broker and pin details
from status_values import MEM  # Ramcheck request (for debug only)

qos = 1 # for test all messages have the same qos

green = pyb.LED(2)
blue = pyb.LED(4)
reset_count = 0

# User tasks. Instantiated as Cancellable tasks: these will be terminated
# with the StopTask exception if the link stops running
@asyn.cancellable
async def ramcheck(mqtt_link):
    while True:
        mqtt_link.command(MEM)
        await asyn.sleep(1800)  # use asyn.sleep() for fast cancellation

@asyn.cancellable
async def publish(mqtt_link, tim):
    count = 1
    while True:
        mqtt_link.publish('result', '{} {}'.format(count, reset_count), 0, qos)
        count += 1
        await asyn.sleep(tim)

async def pulse(led):
    led.on()
    await asyncio.sleep(3)
    led.off()

def cbgreen(topic, msg):
    if msg == 'on':
        green.on()
    elif msg == 'off':
        green.off()
    else:
        print('led value must be "on" or "off"')

# start() is run once communication with the broker has been established and before
# the MQTTlink main loop commences. User tasks should be added here: this ensures
# that they will be restarted if the ESP8266 times out.
# User tasks which run forever must quit on a failure. This is done by trapping
# the StopTask exception.
# Such tasks must update the Barrier instance on exit.

def start(mqtt_link):
    global reset_count
    mqtt_link.subscribe('green', qos, cbgreen)    # LED control qos 1
    loop = asyncio.get_event_loop()
    loop.create_task(asyn.Cancellable(ramcheck, mqtt_link)())  # Check RAM every 30 minutes
    loop.create_task(asyn.Cancellable(publish, mqtt_link, 10)()) # Publish a count every 10 seconds
    loop.create_task(pulse(blue))  # Flash blue LED each time we restart ESP8266
    reset_count += 1

def test():
    MQTTlink.will('result', 'client died')
    init['user_start'] = start
    mqtt_link = MQTTlink(init)  # No. of user tasks
    loop = asyncio.get_event_loop()
    loop.run_forever()

test()
