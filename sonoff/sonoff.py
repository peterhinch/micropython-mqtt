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

from mqtt_as import MQTTClient, config
from config import config
import uasyncio as asyncio
from machine import Pin, Signal

SERVER = '192.168.0.9'  # Change to suit e.g. 'iot.eclipse.org'

led = Signal(Pin(13, Pin.OUT, value = 1), invert = True)
relay = Pin(12, Pin.OUT, value = 0)
led_state = 0
outage = False
outages = 0

M_ON = b'on'
M_OFF = b'off'

def sub_cb(topic, msg):
    global led_state
    if topic == T_RELAY:
        if msg == M_ON or msg == M_OFF:
            relay(msg == M_ON)
    elif topic == T_LED:
        if msg == M_ON or msg == M_OFF:
            led_state = int(msg == M_ON)

async def wifi_han(state):
    global outage, outages
    outage = not state
    if state:
        print('Sonoff: connected to broker.')
    else:
        outages += 1
        print('Sonoff: WiFi or broker is down.')
    await asyncio.sleep(1)

async def led_ctrl():
    while True:
        if outage:
            led(not led())
            await asyncio.sleep_ms(200)
        else:
            led(led_state)
            await asyncio.sleep_ms(50)

async def conn_han(client):
    await client.subscribe(T_LED, 1)
    await client.subscribe(T_RELAY, 1)

async def main(client):
    await client.connect()
    loop = asyncio.get_event_loop()
    loop.create_task(led_ctrl())
    n = 0
    while True:
        await asyncio.sleep(60)
        # If WiFi is down the following will pause for the duration.
        await client.publish(T_RESULT, '{} repubs: {} outages: {}'.format(n, client.REPUB_COUNT, outages), qos = 1)
        n += 1

def run(res_name, led_name, relay_name):
    global T_RESULT, T_LED, T_RELAY
    T_RESULT, T_LED, T_RELAY = res_name, led_name, relay_name

    # Define configuration.
    # Callbacks & coros.
    config['subs_cb'] = sub_cb
    config['wifi_coro'] = wifi_han
    config['connect_coro'] = conn_han
    # MQTT.
    config['will'] = (T_RESULT, 'Goodbye from Sonoff!', False, 0)
    config['server'] = SERVER
    config['keepalive'] = 120
    # The clean settings ensure that commands sent during an outage will be honoured
    # when connectivity resumes.
    config['clean'] = False
    config['clean_init'] = False
    # ping_interval = 5 ensures that LED starts flashing promptly on an outage.
    # This interval is much too fast for a public broker on the WAN.
#    config['ping_interval'] = 5

    # Set up client
#    MQTTClient.DEBUG = True
    client = MQTTClient(config)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main(client))
    finally:  # Prevent LmacRxBlk:1 errors.
        client.close()
