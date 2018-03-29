# net_local.py Local network parameters for Pyboard MQTT link
# Edit for your network. See NO_NET.md for this structure.

# Author: Peter Hinch.
# Copyright Peter Hinch 2017 Released under the MIT license.

# See NO_NET.md para 2.3.1

# If you want to override Pyboard pins:
#from machine import Pin, Signal
from pbmqtt import init

# Customisations: mandatory
init['ssid'] = 'my_ssid'
init['password'] = 'my wifi password'
init['broker'] = 'iot.eclipse.org'

# Optional
init['local_time_offset'] = 1

init['debug'] = True
init['verbose'] = True
