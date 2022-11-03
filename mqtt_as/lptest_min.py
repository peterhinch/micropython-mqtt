# lptest_min.py Test of Feather S2 low power operation
# (C) Copyright Peter Hinch 2022.
# Released under the MIT licence.
from mqtt_as import MQTTClient
from mqtt_local import config
import uasyncio as asyncio
from machine import Pin, ADC, deepsleep, soft_reset
from time import sleep

blue_led = Pin(13, Pin.OUT)
sensor = ADC(Pin(4))  # Light sensor. Light needs to be low to read < 65535.

TOPIC = "shed"  # For demo publication and last will use same topic
debug = True  # In test mode assume a USB connection


def sub_cb(topic, msg, retained):
    debug and print(f'Topic: "{topic.decode()}" Message: "{msg.decode()}" Retained: {retained}')
    blue_led(True)  # Flash LED if subscription received


async def run_task(client):  # deepsleep has ended
    asyncio.wait_for(client.connect(quick=True), 20)  # Can throw OSError or TimeoutError
    await client.subscribe("foo_topic", qos=1)
    await client.publish(TOPIC, f"light {sensor.read_u16():d}", qos=1)
    await asyncio.sleep(1)  # Ensure broker has time to handle subscription
    await client.disconnect()  # Suppress last will
    blue_led(False)


# Timeout limits maximum power consumption in the event of poor connectivity.
# In my testing t/o never triggered. There is a theoretical possibility that
# socket.getaddrinfo() could block forever in poor RSSI conditions.
# TODO How does machine.wdt cope with deepsleep?
async def main(client):
    try:
        await run_task(client)
    except (asyncio.TimeoutError, OSError):  # Mandatory timeout error trapping
        return False  # Connect fail or timeout
    return True


# Define configuration and set up client
config["subs_cb"] = sub_cb
config["will"] = (TOPIC, "Goodbye cruel world!", False, 0)
config["clean"] = False  # Ensure we can receive subscriptions
config["clean_init"] = False  # Exit from deepsleep is like a power cycle
MQTTClient.DEBUG = True  # Enable optional debug statements.
client = MQTTClient(config)


def test(has_usb=True, delay=60, retry=60):
    global debug
    debug = has_usb
    wt = asyncio.run(main(client))  # True == success
    # wt allows different wait time in case of failure.
    client.close()
    tim = delay if wt else retry
    if debug:  # In testing with USB don't deepsleep
        sleep(tim)
        soft_reset()  # Assumes main.py imports this module and calls this function
    deepsleep(tim * 1000)
