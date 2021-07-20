# config.py Local configuration for mqtt_as demo programs.
from sys import platform
from mqtt_as import config

config['server'] = '192.168.0.10'  # Change to suit
# config['server'] = 'iot.eclipse.org'

# Not needed if you're only using ESP8266
config['ssid'] = 'my_SSID'
config['wifi_pw'] = 'my_WiFi_password'

# For demos ensure the same calling convention for LED's on all platforms.
# ESP8266 Feather Huzzah reference board has active low LED's on pins 0 and 2.
# ESP32 is assumed to have user supplied active low LED's on same pins.
# Call with blue_led(True) to light

if platform == 'esp8266' or platform == 'esp32' or platform == 'esp32_LoBo':
    from machine import Pin
    def ledfunc(pin):
        pin = pin
        def func(v):
            pin(not v)  # Active low on ESP8266
        return func
    wifi_led = ledfunc(Pin(0, Pin.OUT, value = 0))  # Red LED for WiFi fail/not ready yet
    blue_led = ledfunc(Pin(2, Pin.OUT, value = 1))  # Message received
elif platform == 'pyboard':
    from pyb import LED
    def ledfunc(led, init):
        led = led
        led.on() if init else led.off()
        def func(v):
            led.on() if v else led.off()
        return func
    wifi_led = ledfunc(LED(1), 1)
    blue_led = ledfunc(LED(3), 0)
