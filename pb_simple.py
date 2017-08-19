# pb_simple.py Minimal publish/subscribe test program for Pyboard MQTT link

# Author: Peter Hinch.
# Copyright Peter Hinch 2017 Released under the MIT license.

# From PC issue (for example)
# Turn the Pyboard green LED on (or off):
# mosquitto_pub -h 192.168.0.9 -t green -m on
# Print publications from the Pyboard:
# mosquitto_sub -h 192.168.0.9 -t result

import pyb
import uasyncio as asyncio
from pbmqtt import MQTTlink
from net_local import init  # Local network, broker and pin details.

green = pyb.LED(2)  # Green: controlled by MQTT messages.
amber = pyb.LED(3)  # On if WiFi up.
qos = 1             # for test all messages have the same qos.

async def publish(mqtt_link, tim):
    count = 1
    egate = mqtt_link.exit_gate  # See docs 2.3.5.
    async with egate:
        while True:
            mqtt_link.publish('result', str(count), 0, qos)
            count += 1
            if not await egate.sleep(tim):
                break

def cbgreen(command, text):
    if text == 'on':
        green.on()
    elif text == 'off':
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
    mqtt_link.subscribe('green', cbgreen, qos)  # LED control qos 1
    mqtt_link.wifi_handler(cbnet)  # Detect WiFi changes
    loop = asyncio.get_event_loop()
    loop.create_task(publish(mqtt_link, 10)) # Publish a count every 10 seconds

MQTTlink.will('result', 'simple client died')
init['user_start'] = start
mqtt_link = MQTTlink(init)
loop = asyncio.get_event_loop()
loop.run_forever()
