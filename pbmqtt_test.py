# pbmqtt_test.py TEST PROGRAM for Pyboard MQTT link
# This tests the ramcheck facility and the mechanism for launching continuously
# running coroutines from the user_start program. Note this is not normally
# recommended.

# Author: Peter Hinch.
# Copyright Peter Hinch 2017 Released under the MIT license.

# From PC issue (for example)
# mosquitto_pub -h 192.168.0.9 -t green -m on
# mosquitto_sub -h 192.168.0.9 -t result

from machine import Pin, Signal
import pyb
import uasyncio as asyncio
from pbmqtt import MQTTlink
from net_local import INIT  # Local network details

green = pyb.LED(2)  # Green
qos = 1 # for test all messages have the same qos
reset_count = 0

# User tasks. Must terminate as soon as link stops running
async def ramcheck(mqtt_link):
    egate = mqtt_link.exit_gate
    async with egate:
        while True:
            mqtt_link.command('mem')
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

async def pulse_blue():
    global reset_count
    reset_count += 1
    blue = pyb.LED(4)
    blue.on()
    await asyncio.sleep(3)
    blue.off()

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
    mqtt_link.subscribe('green', cbgreen, qos)    # LED control qos 1
    loop = asyncio.get_event_loop()
    loop.create_task(ramcheck(mqtt_link))  # Check RAM every 30 minutes
    loop.create_task(publish(mqtt_link, 10)) # Publish a count every 10 seconds
    loop.create_task(pulse_blue())  # Flash blue LED each time we restart ESP8266

def test():
    stx = Pin(Pin.board.Y5, Pin.OUT_PP)         # Define pins
    sckout = Pin(Pin.board.Y6, Pin.OUT_PP, value = 0)
    srx = Pin(Pin.board.Y7, Pin.IN)
    sckin = Pin(Pin.board.Y8, Pin.IN)
    reset = Pin(Pin.board.Y4, Pin.OPEN_DRAIN)
    sig_reset = Signal(reset, invert = True)

    MQTTlink.will('result', 'client died')
    mqtt_link = MQTTlink(sig_reset, sckin, sckout, srx, stx, INIT, start, local_time_offset = 1)
    loop = asyncio.get_event_loop()
    loop.run_forever()

test()
