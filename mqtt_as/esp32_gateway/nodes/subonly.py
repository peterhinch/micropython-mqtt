# subonly.py
# Demonstrate a "subscribe only" micropower application on a UM Feather S3 board.
# Note a publish must be done to trigger reception of any messages. Demo can
# receive "red", "green" or "blue" flashing the NeoPixel accordingly before sleeping
# for 3s.

# Requires AP/router to use a fixed channel, otherwise communications may be lost
# if the AP channel changes after an AP power cycle.
'''
To test need something like
mosquitto_pub -h 192.168.0.10 -t gateway -m '["f412fa420cd4", "red"]' -q 1
'''

import json
from machine import deepsleep, Pin
from neopixel import NeoPixel
from common import gateway, sta, espnow
from time import sleep_ms

np = NeoPixel(Pin(40), 1)  # 1 LED
colors = {"red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255)}

breakout = Pin(8, Pin.IN, Pin.PULL_UP)
if not breakout():  # Debug exit to REPL after boot
    import sys
    sys.exit()

def trigger(espnow):
    message = json.dumps(["dummy", "dummy", False, 0])
    try:
        espnow.send(gateway, message)
    except OSError:  #   # Radio communications with gateway down.
        return
    msg = None
    while True:  # Discard all but last pending message
        mac, content = espnow.recv(200)
        if mac is None:  # Timeout: no pending message from gateway
            break
        msg = content
    try:
        message = json.loads(msg)
    except (ValueError, TypeError):
        return  # No message or bad message
    np[0] = colors[message[1]]
    np.write()
    sleep_ms(500)  # Not micropower but let user see LED

#while True:
    #trigger(espnow)
    #sleep_ms(3000)
trigger(espnow)
espnow.active(False)
sta.active(False)
deepsleep(3_000)
# Now effectively does a hard reset
