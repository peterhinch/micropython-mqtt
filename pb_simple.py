# pb_simple.py Minimal publish/subscribe test program for Pyboard MQTT link

# Author: Peter Hinch.
# Copyright Peter Hinch 2017 Released under the MIT license.

# From PC issue (for example)
# Turn the Pyboard green LED on (or off):
# mosquitto_pub -h 192.168.0.9 -t green -m on
# Check the publications from the Pyboard:
# mosquitto_sub -h 192.168.0.9 -t result

from machine import Pin, Signal
import pyb
import uasyncio as asyncio
from pbmqtt import MQTTlink
from net_local import INIT  # Local network details

green = pyb.LED(2)  # Green
qos = 1 # for test all messages have the same qos

async def publish(mqtt_link, tim):
    count = 1
    while True:
        mqtt_link.publish('result', str(count), 0, qos)
        count += 1
        await asyncio.sleep(tim)

def cbgreen(command, text):
    if text == 'on':
        green.on()
    elif text == 'off':
        green.off()
    else:
        print('led value must be "on" or "off"')

def start(mqtt_link):
    mqtt_link.subscribe('green', cbgreen, qos)    # LED control qos 1

def test():
    stx = Pin(Pin.board.Y5, Pin.OUT_PP)         # Define pins
    sckout = Pin(Pin.board.Y6, Pin.OUT_PP, value = 0)
    srx = Pin(Pin.board.Y7, Pin.IN)
    sckin = Pin(Pin.board.Y8, Pin.IN)
    reset = Pin(Pin.board.Y4, Pin.OPEN_DRAIN)
    sig_reset = Signal(reset, invert = True)

    MQTTlink.will('result', 'simple client died')
    mqtt_link = MQTTlink(sig_reset, sckin, sckout, srx, stx, INIT, start, local_time_offset = 1)
    loop = asyncio.get_event_loop()
    loop.create_task(publish(mqtt_link, 10)) # Publish a count every 10 seconds
    loop.run_forever()

test()
