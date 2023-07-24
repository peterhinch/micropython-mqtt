# alink.py An ESPNow link for asynchronous nodes

# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# Where there are ESP8266 devices the gateway communicates in ap mode.
# Nodes, whether ESP32 or ESP8266, use station mode.

import network
import json
import sys
from .link_setup import *  # Configuration
from .primitives import RingbufQueue
import uasyncio as asyncio
import aioespnow


class ALink:
    GET = json.dumps(["get"])
    AGET = json.dumps(["aget"])
    PING = json.dumps(["ping"])

    def __init__(self, gateway, channel, credentials, debug, poll_interval):
        self.esp = aioespnow.AIOESPNow()
        debug and print("Link init.")
        self._evt_ack = asyncio.Event()
        self._poll_ms = poll_interval
        self._esp_connected = False
        self._wifi_connected = False
        # API: Events may be used by application. If so, app must clear them.
        self.broker_up = asyncio.Event()  # WiFi and broker up
        self.broker_down = asyncio.Event()
        self.esp_up = asyncio.Event()
        self.esp_down = asyncio.Event()
        self.pub_lock = asyncio.Lock()
        self.tx_lock = asyncio.Lock()
        self.reconn = False
        self.channel = channel
        self.gateway = gateway
        self.credentials = credentials
        self.debug = debug
        self.queue = RingbufQueue(10)

    async def reconnect(self):
        esp8266 = sys.platform == "esp8266"
        self.debug and print("connect", self.reconn)
        if self.reconn and channel is not None:
            return  # Nothing to do if channel is fixed.
        sta = network.WLAN(network.STA_IF)
        sta.active(False)
        ap = network.WLAN(network.AP_IF)
        ap.active(False)
        sta.active(True)
        while not sta.active():
            await asyncio.sleep_ms(100)
        if self.channel is None:
            sta.connect(*self.credentials)  # set channel by connecting to AP
            self.debug and print("connecting")
            while not sta.isconnected():
                await asyncio.sleep_ms(100)
        else:
            if esp8266:
                ap.active(True)
                while not ap.active():
                    await asyncio.sleep_ms(100)
                ap.config(channel=self.channel)
                ap.active(False)
            else:
                sta.config(channel=self.channel)
        if  self.debug:
            dev = ap if esp8266 else sta
            print(f"connected on channel {dev.config('channel')}")
        sta.config(pm=sta.PM_NONE)  # No power management
        # For FeatherS3 https://github.com/orgs/micropython/discussions/12017
        if "ESP32-S2" in sys.implementation._machine:
            sta.config(txpower=17)
        self.esp.active(True)
        try:
            self.esp.add_peer(self.gateway)
        except OSError:
            pass  # Already registered
        self.reconn = True
        self.sta = sta


    async def subscribe(self, topic, qos):  # TODO should there be an a_send lock?
        return self._a_send(json.dumps([topic, qos]))

    def _esp_status(self, up):  # Update status of ESPNow interface
        if up:
            self.esp_up.set()
        else:
            self.esp_down.set()
        self._esp_connected = up
        return up

    # Send a message updating the ESPNow status.
    async def _a_send(self, msg):
        async with self.tx_lock:
            res = False
            try:
                res = await self.esp.asend(msg)
            except OSError:
                pass  # Will return False
                # Gateway is OOR, powered down or failed. Or GW not initialised
                # or WiFi not active due to outage recovery in progress.
            return self._esp_status(res)

    # Poll GW periodically to prompt it to send queued messages and to check
    # the status of the ESPNow link. Polling continues at a reduced rate during
    # an outage but must continue to ensure detection of reconnection.
    async def _poll(self):
        while True:
            t = self._poll_ms
            if not await self._a_send(ALink.AGET):
                t *= 4  # Poll less frequently during an outage
            await asyncio.sleep_ms(t)

    # Incoming messages:
    # ACK or NAK: response to publication. NAK means no comms with broker.
    # UP or DOWN: response to poll. DOWN means no comms with broker.
    # Other messages are assumed to be for node to process.
    async def run(self):  # Launched by application. Handles incoming.
        await self.reconnect()
        asyncio.create_task(self._poll())
        async for mac, msg in self.esp:
            cmd = bytes(msg)
            #print("cmd", cmd)
            if cmd == b"ACK":  # Response to publication
                self._evt_ack.set()
            # If cmd == "NAK" let .apublish time out
            if cmd in (b"UP", b"ACK"):
                self.broker_up.set()
                self._wifi_connected = True
            elif cmd in (b"DOWN", b"NAK"):
                self.broker_down.set()
                self._wifi_connected = False
            else:
                try:
                    self.queue.put_nowait(msg)
                except IndexError:
                    pass  # Message loss will occur if app does not remove them promptly

    def __aiter__(self):
        return self

    async def __anext__(self):
        while True:
            msg = await self.queue.get()
            try:
                message = json.loads(msg)
            except ValueError:
                continue
            return message

    async def publish(self, topic, msg, retain=False, qos=0):
        async with self.pub_lock:  # Disallow concurrent pubs
            message = json.dumps([topic, msg, retain, qos])
            while True:
                while not (self._wifi_connected and self._esp_connected):
                    await asyncio.sleep(1)
                self._evt_ack.clear()
                if not await self._a_send(message):
                    continue  # Try again
                await self._evt_ack.wait()  # May be a long wait on outage
                break

    def close(self):
        self.esp.active(False)
        self.sta.active(False)

gwlink = ALink(gateway, channel, credentials, debug, poll_interval)  # From link_setup.py
