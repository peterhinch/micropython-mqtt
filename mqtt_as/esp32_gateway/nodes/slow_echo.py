# slow_echo.py
# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# On ESP8266 need to connect GPIO16 to Rst to wake from deepsleep

'''
Demonstrate a "subscribe only" micropower application on any ESPx target
Echo any incoming message to "shed"
If the AP uses a fixed channel, link_setup should specify the channel.
Otherwise link_setup should provide WiFi credentials.
See pubonly_gen.py for an alternative way to handle variable channels.

To test need something like
mosquitto_pub -h 192.168.0.10 -t foo_topic -m "test message" -q 1
and
mosquitto_sub -h 192.168.0.10 -t shed
'''

from machine import deepsleep, Pin
from time import sleep_ms
from .link import Link
from .link_setup import gateway, channel, credentials  # Args common to all nodes
try:
    gwlink = Link(gateway, channel, credentials)
except OSError:
    deepsleep(3_000)  # Failed to connect. Out of range?

# In micropower mode need a means of getting back to the REPL
# Check the pin number for your harwdware!
#gwlink.breakout(Pin(15, Pin.IN, Pin.PULL_UP))  # Pull down for REPL.

def echo(topic, message, retained):
    gwlink.publish("shed", message)

gwlink.subscribe("foo_topic", 1)
gwlink.get(echo)  # Get any pending messages
gwlink.close()
deepsleep(3_000)
# Now effectively does a hard reset: main.py restarts the application.
