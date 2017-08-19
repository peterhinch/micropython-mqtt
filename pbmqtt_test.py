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
from pbmqtt import MQTTlink
from net_local import init  # Local network, broker and pin details
from status_values import MEM  # Ramcheck request (for debug only)

qos = 1 # for test all messages have the same qos

green = pyb.LED(2)
blue = pyb.LED(4)
reset_count = 0

# User tasks. Must terminate as soon as link stops running
async def ramcheck(mqtt_link):
    egate = mqtt_link.exit_gate
    async with egate:
        while True:
            mqtt_link.command(MEM)
            if not await egate.sleep(1800):
                break

async def publish(mqtt_link, tim):
    count = 1
    egate = mqtt_link.exit_gate
    async with egate:
        while True:
            mqtt_link.publish('result', '{} {}'.format(count, reset_count), 0, qos)
            count += 1
            if not await egate.sleep(tim):
                break

async def pulse(led):
    led.on()
    await asyncio.sleep(3)
    led.off()

def cbgreen(command, text):
    if text == 'on':
        green.on()
    elif text == 'off':
        green.off()
    else:
        print('led value must be "on" or "off"')

# start() is run once communication with the broker has been established and before
# the MQTTlink main loop commences. User tasks should be added here: this ensures
# that they will be restarted if the ESP8266 times out.
# User tasks which run forever must quit on a failure. This is done by waiting on
# the mqtt_link's ExitGate's sleep method, quitting if it returns False

def start(mqtt_link):
    global reset_count
    mqtt_link.subscribe('green', cbgreen, qos)    # LED control qos 1
    loop = asyncio.get_event_loop()
    loop.create_task(ramcheck(mqtt_link))  # Check RAM every 30 minutes
    loop.create_task(publish(mqtt_link, 10)) # Publish a count every 10 seconds
    loop.create_task(pulse(blue))  # Flash blue LED each time we restart ESP8266
    reset_count += 1

def test():
    MQTTlink.will('result', 'client died')
    init['user_start'] = start
    mqtt_link = MQTTlink(init)
    loop = asyncio.get_event_loop()
    loop.run_forever()

test()
