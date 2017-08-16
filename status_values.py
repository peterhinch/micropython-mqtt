# Author: Peter Hinch.
# Copyright Peter Hinch 2017 Released under the MIT license.
# status values for Pyboard MQTT via ESP8266

# ESP8266 has connected to the broker.
BROKER_OK = 0
# ESP8266 is about to connect to the broker.
BROKER_CHECK = 1
# ESP8266 is about to connect to the default network.
DEFNET = 2
# ESP8266 is about to connect to LAN specified in INIT.
SPECNET = 3
# ESP8266 has completed a publication.
PUBOK = 4
# ESP8266 initialisation is complete.
RUNNING = 5
# Fatal. ESP8266 has received an unknown command from host.
UNKNOWN = 6
# ESP8266 has executed a will command.
WILLOK = 7
# Fatal. ESP8266 failed to connect to the broker.
BROKER_FAIL = 8
# ESP8266 reports WiFi up.
WIFI_UP = 9
# ESP8266 reports WiFi down.
# Fatal only during initialisation i.e. when running() returns False.
WIFI_DOWN = 10

# Local status values

# Fatal. ESP8266 has crashed.
ESP_FAIL = 11
# Fatal. keepalive period has elapsed with ESP8266 unable to get a ping
# response from broker. Or it elapsed with no PUBACK from a qos == 1 publish.
NO_NET = 12

# Commands on SynCom link
PUBLISH = 'p'
SUBSCRIBE = 's'
STATUS = 't'
TIME = 'i'
MEM = 'm'
WILL = 'w'
SUBSCRIPTION = 'u'

# Separator
SEP = chr(127)
