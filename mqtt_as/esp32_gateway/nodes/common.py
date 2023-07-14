# common.py Common settings for all nodes

# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# Where there are ESP8266 devices the gateway communicates in ap mode.
# Nodes, whether ESP32 or ESP8266, use station mode.

import network
import espnow
import json
import sys
from time import sleep_ms

# Adapt these lines
gateway = bytes.fromhex(b'2462abe6b0b5')  # ESP reference clone AP I/F
#gateway = bytes.fromhex(b'2462abe6b0b4')  # ESP reference clone Sta I/F
channel = 3  # Router channel or None to use connect
#credentials = ('ssid', 'password')  # Only required if channel is unknown
DEBUG = True

class Link:
    def __init__(self):
        self.reconn = False
        self.channel = channel
        self.reconnect()

    def reconnect(self):
        DEBUG and print("connect", self.reconn)
        if self.reconn and (channel is not None or sys.platform == "esp8266"):
            return  # Nothing to do if channel is fixed. ESP8266 auto-reconnects.
        sta = network.WLAN(network.STA_IF)
        sta.active(False)
        ap = network.WLAN(network.AP_IF)
        ap.active(False)
        sta.active(True)
        while not sta.active():
            sleep_ms(100)
        if channel is None:
            sta.connect(*credentials)  # set channel by connecting to AP
            DEBUG and print("connecting")
            while not sta.isconnected():
                sleep_ms(100)
            DEBUG and print("connected")
        else:
            sta.config(channel=channel)
        sta.config(pm = sta.PM_NONE)  # No power management
        esp = espnow.ESPNow()  # Returns ESPNow object
        esp.active(True)
        try:
            esp.add_peer(gateway)
        except OSError:
            pass  # Already registered
        self.reconn = True
        self.esp = esp
        self.sta = sta

    def send(self, msg):
        return self.esp.send(gateway, msg)

    def recv(self, timeout_ms):
        return self.esp.recv(timeout_ms)

    def subscribe(self, topic, qos):
        return self.send(json.dumps([topic, qos]))

    def close(self):
        self.esp.active(False)
        self.sta.active(False)

link = Link()
