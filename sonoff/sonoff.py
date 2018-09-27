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
# If started with provided topics dictionary:
# sonoff.run()
# test with:
# mosquitto_pub -h 192.168.0.9 -t sonoff_led -q 1 -m on
# mosquitto_pub -h 192.168.0.9 -t sonoff_relay -q 1 -m on
# mosquitto_sub -h 192.168.0.9 -t sonoff_result -q 1

import gc
from micropython_mqtt_as.mqtt_as import MQTTClient, sonoff
from micropython_mqtt_as.config import config

sonoff()  # Specify special handling
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

# Default topic names. Caller can override. Set name to None if unused.
topics = {
    'led': b'sonoff_led',  # Incoming subscriptions
    'relay': b'sonoff_relay',
    'debug': b'sonoff_result',  # Outgoing publications
    'button': b'sonoff_result',
    'remote': b'sonoff_result',  # Set to None if no R/C decoder fitted
    'will': b'sonoff_result',
}


class Sonoff(MQTTClient):
    led = Signal(Pin(13, Pin.OUT, value=1), invert=True)
    relay = Pin(12, Pin.OUT, value=0)
    button = Pushbutton(Pin(0, Pin.IN))
    # Pin 5 on serial connector is GPIO14. Pullup in case n/c
    pin5 = Pin(14, Pin.IN, pull=Pin.PULL_UP)

    def __init__(self, dict_topics):
        self.topics = dict_topics
        # OVERRIDE CONFIG DEFAULTS.
        # Callbacks & coros.
        config['subs_cb'] = self.sub_cb
        config['wifi_coro'] = self.wifi_han
        config['connect_coro'] = self.conn_han
        # MQTT.
        will_topic = self.topics['will']
        if will_topic is not None:
            config['will'] = (will_topic, 'Goodbye from Sonoff!', False, 0)
        config['server'] = SERVER
        config['keepalive'] = 120
        # Setting clean False ensures that commands sent during an outage will be honoured
        # when connectivity resumes.
        config['clean'] = True
        config['clean_init'] = True
        # ping_interval = 5 ensures that LED starts flashing promptly on an outage.
        # This interval is much too fast for a public broker on the WAN.
        #        config['ping_interval'] = 5
        super().__init__(**config)
        if self.topics['button'] is not None:
            # CONFIGURE PUSHBUTTON
            self.button.press_func(self.btn_action, ('Button press',))
            self.button.long_func(self.btn_action, ('Long press.',))
            self.button.double_func(self.btn_action, ('Double click.',))
        self.led_state = 0
        self.outage = True
        self.outages = 0
        self.outage_start = ticks_ms()
        self.max_outage = 0
        if self.topics['remote'] is not None:
            self.ir = NEC_IR(self.pin5, self.rc_cb, True)

    # Publish a message if WiFi and broker is up, else discard.
    def pub_msg(self, topic_name, msg):
        topic = self.topics[topic_name]
        if topic is not None and not self.outage:
            loop.create_task(self.publish(topic, msg, qos=QOS))

    # Callback for message from IR remote.
    def rc_cb(self, data, addr):
        if data == REPEAT:
            msg = 'RC:,Repeat'
        elif data >= 0:
            msg = ','.join(('RC:', hex(data), hex(addr)))
        else:
            msg = ','.join(('RC:,Error', str(data)))
        self.pub_msg('remote', msg)

    # Callback for all pushbutton actions.
    def btn_action(self, msg):
        self.pub_msg('button', msg)

    # Callback for subscribed messages
    def sub_cb(self, topic, msg, retained):
        if topic == self.topics['relay']:
            if msg == M_ON or msg == M_OFF:
                self.relay(int(msg == M_ON))
        elif topic == self.topics['led']:
            if msg == M_ON or msg == M_OFF:
                self.led_state = int(msg == M_ON)

    # Callback when connection established. Create subscriptions.
    async def conn_han(self, _):
        led_topic = self.topics['led']
        if led_topic is not None:
            await self.subscribe(led_topic, QOS)
        relay_topic = self.topics['relay']
        if relay_topic is not None:
            await self.subscribe(relay_topic, QOS)
        self.pub_msg('debug', '(Re)connected to broker.')

    # Callback for changes in WiFi state.
    async def wifi_han(self, state):
        self.outage = not state
        if state:
            duration = ticks_diff(ticks_ms(), self.outage_start) // 1000
            self.max_outage = max(self.max_outage, duration)
            self.pub_msg('debug', 'Network up after {}s down.'.format(duration))
        else:  # Little point in publishing "Network Down"
            self.outages += 1
            self.outage_start = ticks_ms()
        await asyncio.sleep(1)

    # Flash LED if WiFi down, otherwise reflect its current state.
    async def led_ctrl(self):
        while True:
            if self.outage:
                self.led(not self.led())
                await asyncio.sleep_ms(200)
            else:
                self.led(self.led_state)
                await asyncio.sleep_ms(50)

    # Code assumes ESP8266 has stored the WiFi credentials in flash.
    async def main(self):
        loop.create_task(self.led_ctrl())
        sta_if = WLAN(STA_IF)
        conn = False
        while not conn:
            while not sta_if.isconnected():
                await asyncio.sleep(1)
                self.dprint('Awaiting WiFi.')  # Repeats forever if no stored connection.
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
            msg = 'Mins: {} repubs: {} outages: {} RAM free: {} alloc: {} Longest outage: {}s'.format(
                n, self.REPUB_COUNT, self.outages, gc.mem_free(), gc.mem_alloc(), self.max_outage)
            self.pub_msg('debug', msg)
            n += 1


# Topic names in dict enables multiple Sonoff units to run this code. Only main.py differs.


def run(dict_topics=topics):
    MQTTClient.DEBUG = True
    client = Sonoff(dict_topics)
    try:
        loop.run_until_complete(client.main())
    finally:  # Prevent LmacRxBlk:1 errors.
        client.close()
