# pubonly.py
# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# On ESP8266 need to connect GPIO16 to Rst to wake from deepsleep

'''
This is a minimal publish-only demo which publishes random numbers to a topic "shed".
Errors are ignored: if the node moves out of range publications will be lost.
If the AP uses a fixed channel, link_setup should specify the channel.
Otherwise link_setup should provide WiFi credentials.
See pubonly_gen.py for an alternative way to handle variable channels.

To test need something like
mosquitto_sub -h 192.168.0.10 -t shed
'''

from machine import deepsleep, Pin
import os
from .link import Link, PUB_OK
from .link_setup import gateway, channel, credentials  # Args common to all nodes
try:
    gwlink = Link(gateway, channel, credentials)
except OSError:
    deepsleep(3_000)  # Failed to connect. Out of range?

# In micropower mode need a means of getting back to the REPL
# Check the pin number for your harwdware!
# gwlink.breakout(Pin(8, Pin.IN, Pin.PULL_UP))  # Pull down for debug exit to REPL

msg = str(int.from_bytes(os.urandom(2), 'LITTLE'))
gwlink.publish("shed", msg, False, 0)
gwlink.close()
deepsleep(3_000)
# Now effectively does a hard reset: main.py restarts the application.
