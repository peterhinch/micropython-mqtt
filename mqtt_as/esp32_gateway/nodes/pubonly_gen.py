# pubonly.py
# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# A synchronous ESPNOW node publishes the reading of a Feather S3 ambient light sensor.
# If a WiFi/broker outage occurs, messages are lost for the duration.
'''
To test need something like
mosquitto_sub -h 192.168.0.10 -t light
'''

from machine import deepsleep, ADC, Pin
from link import gwlink
from esp32 import NVS
import time
gwlink.breakout(Pin(8, Pin.IN, Pin.PULL_UP))  # Pull down for debug exit to REPL
nvs = NVS('test')
try:
    count = nvs.get_i32('test')
except OSError:
    count = 0
count += 1
nvs.set_i32(count)
nvs.commit()
msg = str(count)

if not gwlink.publish("shed", msg, False, 0):
    np[0] = (255, 0, 0)
    np.write()
    time.sleep_ms(500)
gwlink.close()
deepsleep(3_000)
# Now effectively does a hard reset: main.py restarts the application.
