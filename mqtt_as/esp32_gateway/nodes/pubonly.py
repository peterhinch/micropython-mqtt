# pubonly.py
# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# A synchronous ESPNOW node publishes the reading of a Feather S3 ambient light sensor.
# If a WiFi/broker outage occurs, messages are lost for the duration.
# Requires AP/router to use a fixed channel, otherwise communications may be lost after
# an AP power cycle if the AP channel changes.
'''
To test need something like
mosquitto_sub -h 192.168.0.10 -t light
'''

import json
from machine import deepsleep, ADC, Pin
from common import link

breakout = Pin(8, Pin.IN, Pin.PULL_UP)
if not breakout():  # Debug exit to REPL
    import sys
    sys.exit()

def publish(topic, msg, retain, qos):
    message = json.dumps([topic, msg, retain, qos])
    try:
        link.send(message)
    except OSError:  # Radio communications with gateway down.
        pass

adc = ADC(Pin(4), atten = ADC.ATTN_11DB)
msg = str(adc.read_u16())
publish("light", msg, False, 0)
link.close()
deepsleep(3_000)
# Now effectively does a hard reset
