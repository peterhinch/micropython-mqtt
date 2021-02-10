# hardware.py Local hardware parameters for Pyboard MQTT link

# Author: Peter Hinch.
# Copyright Peter Hinch 2017-2021 Released under the MIT license.

# led is for heartbeat. Omit this key if not required.
from machine import Pin
d = {
    'reset' : Pin(16, Pin.OPEN_DRAIN),
    'stx' : Pin(17, Pin.OUT),
    'sckout' : Pin(18, Pin.OUT, value = 0),
    'srx' : Pin(19, Pin.IN),
    'sckin' : Pin(20, Pin.IN),
    'led' : Pin(25, Pin.OUT),
    }
