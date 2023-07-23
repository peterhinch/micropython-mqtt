# pubonly_gen.py Publish-only node - can run on any ESP32 hardware.
# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# A synchronous ESPNOW node publishes an incrementing count. Counts will be
# lost during an outage.
'''
To test need something like
mosquitto_sub -h 192.168.0.10 -t shed
'''

from machine import deepsleep, ADC, Pin
from link import gwlink
from esp32 import NVS
# In micropower mode need a means of getting back to the REPL
# Check the pin number for your harwdware!
#gwlink.breakout(Pin(8, Pin.IN, Pin.PULL_UP))  # Pull down for debug exit to REPL
nvs = NVS('test')
try:
    count = nvs.get_i32('test')
except OSError:
    count = 0
count += 1
nvs.set_i32(count)
nvs.commit()
msg = str(count)
gwlink.publish("shed", msg, False, 0)
gwlink.close()
deepsleep(3_000)
# Now effectively does a hard reset: main.py restarts the application.
