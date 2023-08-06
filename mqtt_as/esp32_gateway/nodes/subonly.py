# subonly.py
# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# Demonstrate a "subscribe only" micropower application on any ESPx target
# Echo any incoming message to "shed"
# Can operate in micropower mode
'''
To test need something like
mosquitto_pub -h 192.168.0.10 -t allnodes -m "red" -q 1
or
mosquitto_pub -h 192.168.0.10 -t foo_topic -m "green" -q 1
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
while True:
    if not gwlink.get(echo):
       print("Comms fail")
    sleep_ms(3000)
#gwlink.get(echo)  # Get any pending messages
#gwlink.close()
#deepsleep(3_000)
# Now effectively does a hard reset: main.py restarts the application.
