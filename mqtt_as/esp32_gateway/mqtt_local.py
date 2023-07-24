# mqtt_local.py Local configuration for gateway.
from .mqtt_as import config

# Entries must be edited for local conditions
config['server'] = '192.168.0.10'  # Broker
#  config['server'] = 'test.mosquitto.org'

config['ssid'] = 'your_network_name'
config['wifi_pw'] = 'your_password'
