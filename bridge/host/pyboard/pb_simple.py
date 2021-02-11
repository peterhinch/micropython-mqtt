# pb_simple.py Minimal publish/subscribe test program for Pyboard MQTT bridge

# Author: Peter Hinch.
# Copyright Peter Hinch 2017-2021 Released under the MIT license.

# From PC issue (for example)
# Turn the Pyboard green LED on (or off):
# mosquitto_pub -h 192.168.0.10 -t green -m on
# Print publications from the Pyboard:
# mosquitto_sub -h 192.168.0.10 -t result

import pyb
import uasyncio as asyncio
from pbmqtt import MQTTlink
import hardware  # Pin definitions
import net_local  # WiFi credentials

green = pyb.LED(2)  # Green: controlled by MQTT messages.
amber = pyb.LED(3)  # On if WiFi up.
qos = 1  # for test all messages have the same qos.

async def publish(mqtt_link, tim):
    count = 1
    while True:
        await mqtt_link.publish('result', str(count), False, qos)
        count += 1
        await asyncio.sleep(tim)

def cbgreen(topic, msg, retained):
    if msg == 'on':
        green.on()
    elif msg == 'off':
        green.off()
    else:
        print('led value must be "on" or "off"')

def cbnet(state, _):  # Show WiFi state. Discard mqtt_link arg.
    amber.on() if state else amber.off()

async def main(mqtt_link):
    asyncio.create_task(mqtt_link.subscribe('green', qos, cbgreen))  # LED control qos 1
    asyncio.create_task(publish(mqtt_link, 10))
    while True:
        await asyncio.sleep(10)

MQTTlink.will('result', 'simple client died')
mqtt_link = MQTTlink(hardware.d, net_local.d, wifi_handler=(cbnet,()), debug=True, verbose=True)
try:
    asyncio.run(main(mqtt_link))
finally:
    asyncio.new_event_loop()
