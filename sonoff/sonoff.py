# sonoff.py Control Sonoff LED and relay remotely.
# (C) Copyright Peter Hinch 2017.

# The MIT License (MIT)
#
# Copyright (c) 2017 Peter Hinch
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# Public brokers https://github.com/mqtt/mqtt.github.io/wiki/public_brokers

# Publishes connection statistics.
# mosquitto_pub -h 192.168.0.9 -t sonoff_led -q 1 -m on
# mosquitto_pub -h 192.168.0.9 -t sonoff_relay -q 1 -m on
# mosquitto_sub -h 192.168.0.9 -t sonoff_result -q 1

import gc
from mqtt_as import MQTTClient, config
gc.collect()
import uasyncio as asyncio
from machine import Pin, Signal
from aswitch import Pushbutton
gc.collect()
from aremote import *
from network import WLAN, STA_IF
from utime import ticks_ms, ticks_diff
gc.collect()

SERVER = '192.168.0.9'  # Change to suit e.g. 'iot.eclipse.org'

loop = asyncio.get_event_loop()

M_ON = b'on'
M_OFF = b'off'
QOS = 1

class Sonoff(MQTTClient):
    led = Signal(Pin(13, Pin.OUT, value = 1), invert = True)
    relay = Pin(12, Pin.OUT, value = 0)
    button = Pushbutton(Pin(0, Pin.IN))
    # Pin 5 on serial connector is GPIO14
    pin5 = Pin(14, Pin.IN)
    def __init__(self, res_name, led_name, relay_name):
        self.T_RESULT, self.T_LED, self.T_RELAY = res_name, led_name, relay_name
        # OVERRIDE CONFIG DEFAULTS.
        # Callbacks & coros.
        config['subs_cb'] = self.sub_cb
        config['wifi_coro'] = self.wifi_han
        config['connect_coro'] = self.conn_han
        # MQTT.
        config['will'] = (self.T_RESULT, 'Goodbye from Sonoff!', False, 0)
        config['server'] = SERVER
        config['keepalive'] = 120
        # The clean settings ensure that commands sent during an outage will be honoured
        # when connectivity resumes.
        config['clean'] = False
        config['clean_init'] = False
        # ping_interval = 5 ensures that LED starts flashing promptly on an outage.
        # This interval is much too fast for a public broker on the WAN.
#        config['ping_interval'] = 5
        super().__init__(config)
        # CONFIGURE PUSHBUTTON
        self.button.press_func(self.btn_action, ('Button press',))
        self.button.long_func(self.btn_action, ('Long press.',))
        self.button.double_func(self.btn_action, ('Double click.',))
        self.led_state = 0
        self.outage = True
        self.outages = 0
        self.outage_start = ticks_ms()
        self.max_outage = 0
        ir = NEC_IR(self.pin5, self.rc_cb, True)

    # Publish a message if WiFi and broker is up, else discard.
    def pub_msg(self, msg):
        if not self.outage:
            loop.create_task(self.publish(self.T_RESULT, msg, qos = QOS))

    def rc_cb(self, data, addr):
        if data == REPEAT:
            msg = 'RC:,Repeat'
        elif data >= 0:
            msg = ','.join(('RC:', hex(data), hex(addr)))
        self.pub_msg(msg)

    def btn_action(self, msg):
        self.pub_msg(msg)

    def sub_cb(self, topic, msg):
        if topic == self.T_RELAY:
            if msg == M_ON or msg == M_OFF:
                self.relay(int(msg == M_ON))
        elif topic == self.T_LED:
            if msg == M_ON or msg == M_OFF:
                self.led_state = int(msg == M_ON)

    async def conn_han(self, _):
        await self.subscribe(self.T_LED, QOS)
        await self.subscribe(self.T_RELAY, QOS)
        self.pub_msg('(Re)connected to broker.')

    async def wifi_han(self, state):
        self.outage = not state
        if state:
            duration = ticks_diff(ticks_ms(), self.outage_start) // 1000
            self.max_outage = max(self.max_outage, duration)
            self.pub_msg('Network up after {}s down.'.format(duration))
        else:  # Little point in publishing "Network Down"
            self.outages += 1
            self.outage_start = ticks_ms()
        await asyncio.sleep(1)

    async def led_ctrl(self):
        while True:
            if self.outage:
                self.led(not self.led())
                await asyncio.sleep_ms(200)
            else:
                self.led(self.led_state)
                await asyncio.sleep_ms(50)

    async def main(self):
        loop.create_task(self.led_ctrl())
        sta_if = WLAN(STA_IF)
        conn = False
        while not conn:
            while not sta_if.isconnected():
                await asyncio.sleep(1)
                self.dprint('Awaiting WiFi.')
            await asyncio.sleep(3)
            try:
                await self.connect()
                conn = True
            except OSError:
                self.close()  # Close socket
                self.dprint('Awaiting broker.')

        self.dprint('Starting.')
        self.outage = False
        n = 0
        while True:
            await asyncio.sleep(60)
            gc.collect()  # For RAM stats.
            msg = 'Mins: {} repubs: {} outages: {} RAM free: {} alloc: {} Max outage: {}'.format(
                n, self.REPUB_COUNT, self.outages, gc.mem_free(), gc.mem_alloc(), self.max_outage)
            self.pub_msg(msg)
            n += 1


def run(res_name, led_name, relay_name):
    MQTTClient.DEBUG = True
    client = Sonoff(res_name, led_name, relay_name)
    try:
        loop.run_until_complete(client.main())
    finally:  # Prevent LmacRxBlk:1 errors.
        client.close()
