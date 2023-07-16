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
from link import link
from time import sleep_ms

# In micropower mode need a means of getting back to the REPL
# Check the pin number for your harwdware!
#link.breakout(Pin(15, Pin.IN, Pin.PULL_UP))  # Pull down for REPL.

def echo(topic, message, retained):
    link.publish("shed", message)


link.subscribe("foo_topic", 1)
while True:
    if not link.get(echo):
       print("Comms fail")
    sleep_ms(3000)
#link.get(echo)  # Get any pending messages
#link.close()
#deepsleep(3_000)
# Now effectively does a hard reset: main.py restarts the application.
