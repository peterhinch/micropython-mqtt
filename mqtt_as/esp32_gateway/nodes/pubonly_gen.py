# pubonly_gen.py Publish-only node - can run on any ESP32 or ESP8266 hardware.
# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# On ESP8266 need to connect GPIO16 to Rst to wake from deepsleep

# A synchronous ESPNOW node publishes an incrementing count, then sleeps.
# main.py wakes it.
# Channel selection: 
# 1. If a channel number is passed, it is used and assumed to be fixed.
# 2. If channel is None but credentials are passed, connects to WiFi.
# 3. If channel is None and credentials is None, scans channels.
# Cases 2 and 3 recover from channel changes by detecting repeated pub fails.
# In this instance a reconnect attempt is triggered.

'''
To test need something like
mosquitto_sub -h 192.168.0.10 -t shed
'''

from machine import deepsleep, Pin, RTC
import json
from .link import Link, PUB_OK
from .link_setup import gateway, channel, credentials  # Args common to all nodes
rtc = RTC()
count = 0
errcount = 0
if channel is None and (mem := rtc.memory()):  # There is a stored channel
    count, errcount, channel = json.loads(mem)  # Use last channel
    if errcount > 5:  # unless there were repeated failures
        channel = None  # Force a detection

try:
    gwlink = Link(gateway, channel, credentials)
except OSError:
    deepsleep(3_000)  # Failed to connect. Out of range?

# In micropower mode need a means of getting back to the REPL
# Check the pin number for your harwdware!
#gwlink.breakout(Pin(8, Pin.IN, Pin.PULL_UP))  # Pull down for debug exit to REPL

if gwlink.publish("shed", f"Count {count} Error sequence {errcount}", False, 0) == PUB_OK:
    errcount = 0
    count += 1
else:
    errcount += 1
rtc.memory(json.dumps([count, errcount, gwlink.cur_chan]))
gwlink.close()
deepsleep(3_000)
# Now effectively does a hard reset: main.py restarts the application.
