# common.py Common settings for all nodes

# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# Where there are ESP8266 devices the gateway communicates in ap mode.
# Nodes, whether ESP32 or ESP8266, use station mode.

import network
import json
import sys
from time import sleep_ms
from link_setup import *  # Configuration
try:
    import aioespnow as espnow
    debug and print("Synchronous and async mode.")
except ImportError:
    import espnow
    debug and print("Synchronous mode.")

class Link:
    GET = json.dumps(["get"])
    PING = json.dumps(["ping"])

    def __init__(self, gateway, channel, credentials, debug):
        self.reconn = False
        self.channel = channel
        self.gateway = gateway
        self.credentials = credentials
        self.debug = debug
        self.reconnect()

    def reconnect(self):
        self.debug and print("connect", self.reconn)
        if self.reconn and (channel is not None or sys.platform == "esp8266"):
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
            self.debug and print("connected")
        else:
            if sys.platform == "esp8266":
                ap.active(True)
                while not ap.active():
                    sleep_ms(100)
                ap.config(channel=self.channel)
                ap.active(False)
            else:
                sta.config(channel=self.channel)
        sta.config(pm=sta.PM_NONE)  # No power management
        esp = espnow.ESPNow()
        esp.active(True)
        try:
            esp.add_peer(self.gateway)
        except OSError:
            pass  # Already registered
        self.reconn = True
        self.esp = esp
        self.sta = sta

    def send(self, msg):  # Should be a JSON encoded list of length 1, 2 or 4.
        return self.esp.send(self.gateway, msg)

    def recv(self, timeout_ms):
        return self.esp.recv(timeout_ms)

    def subscribe(self, topic, qos):
        return self.send(json.dumps([topic, qos]))

    def publish(self, topic, msg, retain=False, qos=0, subs=None):
        message = json.dumps([topic, msg, retain, qos])
        got_ack = not qos & 4  # False if ACK required and not yet received
        connected = True  # Assume OK
        try:
            if not self.send(message):
                return False
            while True:  # Process pending messages. Must wait for possible outage msg.
                mac, msg = self.recv(200)
                if mac is None:  # Timeout: no pending message from gateway
                    if not got_ack:
                        return False
                    return connected
                message = json.loads(msg)  # No need for try: never get corrupted msg
                topic = message[0]
                if topic == "ACK":
                    got_ack = True
                elif topic == "OUT":  # WiFi/broker fail
                    connected = False
                # Run subscription callback
                elif len(message) == 3 and subs is not None:
                    subs(*message)  # callback(topic, msg, retained)
        except OSError:  # Radio communications with gateway down.
            pass
        return False

    def ping(self):
        return self.send(Link.PING)  # Quick connectivity check

    def get(self, subs):
        if self.send(Link.GET):
            mac = 1
            while mac is not None:  # Until out of messages
                mac, msg = self.recv(200)  # mac == None on timeout
                if mac is not None:
                    message = json.loads(msg)
                    subs(*message)  # callback(topic, msg, retained)
            return True
        return False  # Comms fail

    def close(self):
        self.esp.active(False)
        self.sta.active(False)

    def breakout(self, pin):
        if not pin():
            sys.exit(0)

    # asyncio support
    def __aiter__(self):
        return self

    async def __anext__(self):
        mac, msg = await self.esp.arecv()
        return json.loads(msg)

    async def apublish(self, topic, msg, retain=False, qos=0):
        message = json.dumps([topic, msg, retain, qos])
        got_ack = not qos & 4  # False if ACK required and not yet received
        connected = True  # Assume OK
        try:
            if not await self.asend(message):
                return False
            while True:  # Process pending messages. Must wait for possible outage msg.
                try:
                    mac, msg = asyncio.wait_for_ms(self.esp.arecv(), 500)
                except asyncio.TimeoutError:
                    if not got_ack:
                        return False
                    return connected
                message = json.loads(msg)  # No need for try: never get corrupted msg
                topic = message[0]
                if topic == "ACK":
                    got_ack = True
                elif topic == "OUT":  # WiFi/broker fail
                    connected = False
        except OSError:  # Radio communications with gateway down.
            pass
        return False

link = Link(gateway, channel, credentials, debug)  # From node_setup.py
