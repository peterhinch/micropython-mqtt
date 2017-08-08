# net_local.py Local network parameters for Pyboard MQTT link
# Edit for your network. See NO_NET.md for this structure.

# Author: Peter Hinch.
# Copyright Peter Hinch 2017 Released under the MIT license.

# See NO_NET.md para 2.3.1

INIT = (
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
    0           # Clean Session 1/0
    )
