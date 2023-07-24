# pubonly.py
# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# A synchronous ESPNOW node publishes the reading of a Feather S3 ambient light sensor.
# If a WiFi/broker outage occurs, messages are lost for the duration.
'''
To test need something like
mosquitto_sub -h 192.168.0.10 -t light
'''

from machine import deepsleep, ADC, Pin
from .link import gwlink
from neopixel import NeoPixel
import time
# In micropower mode need a means of getting back to the REPL
# Check the pin number for your harwdware!
# gwlink.breakout(Pin(8, Pin.IN, Pin.PULL_UP))  # Pull down for debug exit to REPL
np = NeoPixel(Pin(40), 1)

adc = ADC(Pin(4), atten = ADC.ATTN_11DB)
msg = str(adc.read_u16())
if not gwlink.publish("light", msg, False, 0):
    np[0] = (255, 0, 0)
    np.write()
    time.sleep_ms(500)
gwlink.close()
deepsleep(3_000)
# Now effectively does a hard reset: main.py restarts the application.
