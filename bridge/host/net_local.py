# net_local.py Local network parameters for Pyboard MQTT link
# Edit for your network. See BRIDGE.md for this structure.

# Author: Peter Hinch.
# Copyright Peter Hinch 2017-2021 Released under the MIT license.

# See BRIDGE.md para 2.3.1

d = {
    # Customisations: mandatory
    'ssid' : 'my_ssid',
    'password' : 'my_password',
    'broker' : '192.168.0.10',
    }
# or e.g. 'broker' : 'test.mosquitto.org'
