from mqtt_as import config
from sys import platform

# Include any cross-project settings.

if platform == 'esp32':
    config['ssid'] = 'my SSID'  # EDIT if you're using ESP32
    config['wifi_pw'] = 'my WiFi password'
