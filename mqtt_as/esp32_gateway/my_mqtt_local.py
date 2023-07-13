# config.py Local configuration for gateway with relative import
from sys import platform, implementation
from .mqtt_as import config

config['server'] = '192.168.0.10'  # Change to suit
#  config['server'] = 'test.mosquitto.org'

# Not needed if you're only using ESP8266
config['ssid'] = 'misspiggy'
config['wifi_pw'] = '6163VMiqSTyx'
