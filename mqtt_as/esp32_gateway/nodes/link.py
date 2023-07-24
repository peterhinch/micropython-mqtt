# link.py An ESPNow link for synchronous nodes

# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# Where there are ESP8266 devices the gateway communicates in ap mode.
# Nodes, whether ESP32 or ESP8266, use station mode.

import network
import json
import sys
from time import sleep_ms
import espnow
from .link_setup import *  # Configuration
from .primitives import RingbufQueue


class Link:
    GET = json.dumps(["get"])
    PING = json.dumps(["ping"])

    def __init__(self, gateway, channel, credentials, debug):
        self.esp = espnow.ESPNow()
        debug and print("Link init.")
        self.reconn = False
        self.channel = channel
        self.gateway = gateway
        self.credentials = credentials
        self.debug = debug
        self.queue = RingbufQueue(10)
        self.reconnect()

    def reconnect(self):
        esp8266 = sys.platform == "esp8266"
        self.debug and print(f"{'Reconnectig' if self.reconn else 'Connecting'}")
        if self.reconn and (channel is not None or esp8266):
            return  # Nothing to do if channel is fixed. ESP8266 auto-reconnects.
        sta = network.WLAN(network.STA_IF)
        sta.active(False)
        ap = network.WLAN(network.AP_IF)
        ap.active(False)
        sta.active(True)
        while not sta.active():
            sleep_ms(100)
        if self.channel is None:
            sta.connect(*self.credentials)  # set channel by connecting to AP
            self.debug and print("connecting")
            while not sta.isconnected():
                sleep_ms(100)
        else:
            if esp8266:
                ap.active(True)
                while not ap.active():
                    sleep_ms(100)
                ap.config(channel=self.channel)
                ap.active(False)
            else:
                sta.config(channel=self.channel)
        if  self.debug:
            dev = ap if esp8266 else sta
            print(f"connected on channel {dev.config('channel')}")
        sta.config(pm=sta.PM_NONE)  # No power management
        # For FeatherS3 https://github.com/orgs/micropython/discussions/12017
        if "ESP32-S3" in sys.implementation._machine:
            sta.config(txpower=17)
        self.esp.active(True)
        try:
            self.esp.add_peer(self.gateway)
        except OSError:
            pass  # Already registered
        self.reconn = True
        self.sta = sta

    def send(self, msg):  # Should be a JSON encoded list of length 1, 2 or 4.
        return self.esp.send(self.gateway, msg)

    def recv(self, timeout_ms):
        return self.esp.recv(timeout_ms)

    def subscribe(self, topic, qos):
        return self.send(json.dumps([topic, qos]))

    def publish(self, topic, msg, retain=False, qos=0):
        message = json.dumps([topic, msg, retain, qos])
        try:
            if not self.send(message):
                return False
            while True:
                mac, msg = self.recv(200)  # receive exactly one message (fast, low power)
                if mac is None:  # Timeout: no response from gateway
                    return False
                if msg == b"ACK":
                    return True
                if msg == b"NAK":
                    return False
                # There is a chance that an unsolicited message arrives before the ack
                try:
                    self.queue.put_nowait(msg)
                except IndexError:
                    pass
        except OSError:  # Radio communications with gateway down.
            pass
        return False

    def ping(self):
        if self.send(Link.PING):
            mac, msg = self.recv(200)
            if mac is not None:
                return msg  # b"UP" or b"DOWN" depending on broker status
        return b"FAIL"  # ESPNow comms fail

    def get(self, subs):
        if self.send(Link.GET):
            q = self.queue  # Handle any queued messages
            while q.qsize():
                msg = q.get_nowait()
                try:
                    message = json.loads(msg)
                except ValueError:
                    pass
                else:
                    subs(*message)  # callback(topic, msg, retained)
            mac = 1
            while mac is not None:  # Until out of messages
                mac, msg = self.recv(200)  # mac == None on timeout
                if mac is not None:
                    try:
                        message = json.loads(msg)
                    except ValueError:  # Occured after a gateway outage
                        pass
                    else:
                        subs(*message)  # callback(topic, msg, retained)
            return True
        return False  # Comms fail

    def close(self):
        self.esp.active(False)
        self.sta.active(False)

    def breakout(self, pin):
        if not pin():
            sys.exit(0)


gwlink = Link(gateway, channel, credentials, debug)
