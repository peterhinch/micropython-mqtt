# pubonly.py
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
from common import gateway, sta, espnow
breakout = Pin(8, Pin.IN, Pin.PULL_UP)
if not breakout():  # Debug exit to REPL
    import sys
    sys.exit()

def publish(espnow, topic, msg, retain, qos):
    message = json.dumps([topic, msg, retain, qos])
    try:
        espnow.send(gateway, message)
    except OSError:  # Radio communications with gateway down.
        pass

adc = ADC(Pin(4), atten = ADC.ATTN_11DB)
msg = str(adc.read_u16())
publish(espnow, "light", msg, False, 0)
espnow.active(False)
sta.active(False)
deepsleep(3_000)
# Now effectively does a hard reset
