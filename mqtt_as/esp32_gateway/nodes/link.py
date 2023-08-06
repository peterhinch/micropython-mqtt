# link.py An ESPNow link for synchronous nodes

# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# Where there are ESP8266 devices the gateway communicates in ap mode.
# Nodes, whether ESP32 or ESP8266, use station mode.

import network
import json
import sys
from time import sleep_ms, ticks_ms, ticks_diff
import espnow
from .link_setup import *  # Configuration
from .primitives import RingbufQueue

PUB_OK = const(0)
BROKER_OUT = const(1)
ESP_FAIL = const(2)
PUB_FAIL = const(3)

# For FeatherS3 see https://github.com/orgs/micropython/discussions/12017
# Board releases prior to P8 or U8 set txpower=17

# Micropower apps either set channel=N if known else set channel=None and credentials=None
# In this case channel is found by testing each one for a response from gateway.
# Strategies include initially setting channel=None, storing the outcome in RTC RAM.
# Repeated errors provoke re-trying with None

class Link:
    GET = json.dumps(["get"])
    PING = json.dumps(["ping"])
    CHAN = json.dumps(["chan"])
    txpower = None  # Set to 17 before instantiating for early FeatherS3 boards

    def __init__(self, gateway, channel, credentials, debug=True):
        self.esp = espnow.ESPNow()
        debug and print("Link init.")
        self.channel = channel  # Channel specified by ctor
        self.gateway = bytes.fromhex(gateway)
        self.credentials = credentials
        self.debug = debug
        self.queue = RingbufQueue(10)
        self.cur_chan = self.reconnect()  # Actual channel

    def reconnect(self):
        esp8266 = sys.platform == "esp8266"
        channel = self.channel
        self.debug and print(f"reconnect chan {self.channel} creds {self.credentials}")
        sta = network.WLAN(network.STA_IF)
        self.sta = sta
        sta.active(True)
        while not sta.active():
            sleep_ms(100)
        ap = network.WLAN(network.AP_IF)
        self.ap = ap
        if esp8266:
            ap.active(True)
            while not ap.active():
                sleep_ms(100)
            dev = ap
        else:
            dev = sta
            ap.active(False)

        # Determine channel to use
        if isinstance(channel, int):  # Channel is fixed
            dev.config(channel=channel)
        elif isinstance(credentials, tuple):  # Find chan by connect
            sta.connect(*self.credentials)
            self.debug and print("Link connecting to AP")
            start = ticks_ms()
            while not sta.isconnected():
                sleep_ms(100)
                if ticks_diff(ticks_ms(), start) > 5_000:
                    raise OSError("Wifi connect fail")
        else:  # Try all channels
            self.debug and print("Testing channels")
            channel = self.find_channel(dev)
            if channel is None:
                raise OSError("Connect fail")
        self.debug and print(f"connected on channel {dev.config('channel')}")

        sta.config(pm=sta.PM_NONE)  # No power management
        if Link.txpower is not None:
            sta.config(txpower=self.txpower)
        self.init_esp()
        ap.active(False)
        return channel

    def init_esp(self):
        self.esp.active(True)
        try:
            self.esp.add_peer(self.gateway)
        except OSError:
            pass  # Already registered

    def send(self, msg):  # Should be a JSON encoded list of length 1, 2 or 4.
        try:
            return self.esp.send(self.gateway, msg)
        except OSError as e:
            return False

    def recv(self, timeout_ms):
        return self.esp.recv(timeout_ms)

    def subscribe(self, topic, qos):
        return self.send(json.dumps([topic, qos]))

    def publish(self, topic, msg, retain=False, qos=0):
        message = json.dumps([topic, msg, retain, qos])
        try:
            if not self.send(message):
                return ESP_FAIL
            while True:
                mac, msg = self.recv(200)  # receive exactly one message (fast, low power)
                if mac is None:  # Timeout: no response from gateway
                    return False
                if msg == b"ACK":
                    return PUB_OK
                if msg == b"NAK":  # pubq is half full: broker is down
                    return BROKER_OUT
                if msg == b"BAD":  # pubq is full: message lost
                    return PUB_FAIL
                # There is a chance that an unsolicited message arrives before the ack
                try:
                    self.queue.put_nowait(msg)
                except IndexError:
                    pass
        except OSError:  # Radio communications with gateway down.
            pass
        return ESP_FAIL

    def ping(self):
        if self.send(Link.PING):
            mac, msg = self.recv(200)
            if mac is not None:
                return PUB_OK if msg == b"UP" else PUB_FAIL  # depending on broker status
        return ESP_FAIL  # ESPNow comms fail

    def get_channel(self):  # Return channel no. or None on failure
        if self.send(Link.CHAN):
            mac, msg = self.recv(200)
            if mac is not None:
                try:
                    return int(msg)
                except ValueError:
                    pass

    def find_channel(self, dev):
        self.init_esp()
        for channel in range(1, 14):
            self.debug and print(f"Testing channel {channel}")
            dev.config(channel=channel)
            if (ch := self.get_channel()) is not None:
                dev.config(channel=ch)  # Connect on returned channel
                return ch  # Otherwise return None on failure

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
        self.ap.active(False)

    def breakout(self, pin):
        if not pin():
            sys.exit(0)


