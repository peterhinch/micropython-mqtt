# net_local.py Local network parameters for Pyboard MQTT link
# Edit for your network. See NO_NET.md for this structure.

# Author: Peter Hinch.
# Copyright Peter Hinch 2017 Released under the MIT license.

# See NO_NET.md para 2.3.1

from machine import Pin, Signal

_INIT = (
    'init',     # Must read 'init'
    'my_SSID',  # WiFi and broker details. CHANGE THESE.
    'my_password',
    'broker_ip_address',
    '',         # MQTT username (or '')
    '',         # MQTT password
    repr({}),   # SSL params
    1,          # Use default net (1/0) see docs.
    0,          # Port (0 == use default)
    0,          # Use SSL (1/0)
    1,          # Clock ESP8266 at 80/160MHz (0/1)
    3600,       # RTC resync time (s)
    60,         # Keepalive time (s)
    0,          # Clean Session (1/0)
    1           # Emit debug messages from ESP8266 on UART (1/0)
    )

# Define pin numbers, optional time offset.
init_args = {
    'stx'    : Pin(Pin.board.Y5, Pin.OUT_PP),
    'sckout' : Pin(Pin.board.Y6, Pin.OUT_PP, value = 0),
    'srx'    : Pin(Pin.board.Y7, Pin.IN),
    'sckin'  : Pin(Pin.board.Y8, Pin.IN),
    'reset'  : Signal(Pin(Pin.board.Y4, Pin.OPEN_DRAIN), invert = True),
    'init'   : _INIT,
    'local_time_offset' : 1  # BST = GMT + 1 hour
    }
