# hardware.py Local hardware parameters for Pyboard MQTT link

# Author: Peter Hinch.
# Copyright Peter Hinch 2017-2021 Released under the MIT license.

# led is for heartbeat. Omit this key if not required.
from machine import Pin
d = {
    'reset' : Pin(Pin.board.Y4, Pin.OPEN_DRAIN),
    'stx' : Pin(Pin.board.Y5, Pin.OUT),
    'sckout' : Pin(Pin.board.Y6, Pin.OUT, value = 0),
    'srx' : Pin(Pin.board.Y7, Pin.IN),
    'sckin' : Pin(Pin.board.Y8, Pin.IN),
    'led' : Pin(Pin.board.LED_RED, Pin.OUT),
    }
