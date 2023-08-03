# pubonly.py
# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# A synchronous ESPNOW node publishes the reading of a Feather S3 ambient light sensor.
# If a WiFi/broker outage occurs, messages are lost for the duration.
'''
To test need something like
mosquitto_sub -h 192.168.0.10 -t light

Micropower apps where channel may vary need to instantiate gwlink with channel=None. Slow
and power hungry. Can reduce on time of subsequent runs by saving gwlink.last_channel to a file.
On first run the file does not exist, so instantiate link with channel=None and credentials.
On subsequent runs, retrieve the channel from the file.
Need a mechanism where, if successive runs fail, the file is deleted.
'''

from machine import deepsleep, ADC, Pin
from neopixel import NeoPixel
import time
from .link import Link
from .link_setup import gateway, channel, credentials  # Args common to all nodes
gwlink = Link(gateway, channel, credentials)

# In micropower mode need a means of getting back to the REPL
# Check the pin number for your harwdware!
gwlink.breakout(Pin(8, Pin.IN, Pin.PULL_UP))  # Pull down for debug exit to REPL
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
