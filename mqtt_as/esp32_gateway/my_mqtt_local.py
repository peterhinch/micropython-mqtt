# config.py Local configuration for mqtt_as demo programs.
from sys import platform, implementation
from mqtt_as import config

config['server'] = '192.168.0.10'  # Change to suit
#  config['server'] = 'test.mosquitto.org'

# Not needed if you're only using ESP8266
config['ssid'] = 'misspiggy'
config['wifi_pw'] = '6163VMiqSTyx'
# Use with gateway only:
config['gwtopic'] = (("gateway", 1),)

# For demos ensure same calling convention for LED's on all platforms.
# ESP8266 Feather Huzzah reference board has active low LED's on pins 0 and 2.
# ESP32 is assumed to have user supplied active low LED's on same pins.
# Call with blue_led(True) to light

from machine import Pin
def ledfunc(pin, active=0):
    pin = pin
    def func(v):
        pin(not v)  # Active low on ESP8266
    return pin if active else func
#wifi_led = ledfunc(Pin(0, Pin.OUT, value = 0))  # Red LED for WiFi fail/not ready yet
wifi_led = lambda _ : None
#blue_led = ledfunc(Pin(2, Pin.OUT, value = 1))  # Message received
blue_led = ledfunc(Pin(13, Pin.OUT, value = 0), 1)  # Message received ESP32-S3
