# pb_simple.py Minimal publish/subscribe test program for Pyboard MQTT link

# Author: Peter Hinch.
# Copyright Peter Hinch 2017-2018 Released under the MIT license.

# From PC issue (for example)
# Turn the Pyboard green LED on (or off):
# mosquitto_pub -h 192.168.0.9 -t green -m on
# Print publications from the Pyboard:
# mosquitto_sub -h 192.168.0.9 -t result

import pyb
import uasyncio as asyncio
from pbmqtt import MQTTlink
from net_local import init  # Local network, broker and pin details.
import asyn

green = pyb.LED(2)  # Green: controlled by MQTT messages.
amber = pyb.LED(3)  # On if WiFi up.
qos = 1             # for test all messages have the same qos.

@asyn.cancellable
async def publish(mqtt_link, tim):
    count = 1
    while True:
        mqtt_link.publish('result', str(count), 0, qos)
        count += 1
        await asyn.sleep(tim)  # Use asyn.sleep for fast response to StopTask

def cbgreen(topic, msg):
    if msg == 'on':
        green.on()
    elif msg == 'off':
        green.off()
    else:
        print('led value must be "on" or "off"')

def cbnet(state):
    if state:
        amber.on()
    else:
        amber.off()

# The user_start callback. See docs 2.3.5.
def start(mqtt_link):
    mqtt_link.subscribe('green', qos, cbgreen)  # LED control qos 1
    mqtt_link.wifi_handler(cbnet)  # Detect WiFi changes
    loop = asyncio.get_event_loop()
    loop.create_task(asyn.Cancellable(publish, mqtt_link, 10)()) # Publish a count every 10 seconds

MQTTlink.will('result', 'simple client died')
init['user_start'] = start
mqtt_link = MQTTlink(init)
loop = asyncio.get_event_loop()
loop.run_forever()
