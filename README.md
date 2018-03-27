# Introduction

MQTT is an easily used networking protocol designed for IOT (internet of
things) applications. It is well suited for controlling hardware devices and
for reading sensors across a local network or the internet.

It is a means of communicating between multiple clients. A single server, also
known as a broker, manages the network. Clients may include ESP8266 modules or
other networked computers. Typical server hardware is a Raspberry Pi or other
small Linux machine which may be left running 24/7. Public brokers
[also exist](https://github.com/mqtt/mqtt.github.io/wiki/public_brokers).

An effective PC client and server is [mosquitto](https://mosquitto.org/).

# This repository

This contains two separate projects:  
 1. A "resilient" asynchronous non-blocking MQTT driver.
 2. A means of using a cheap ESP8266 module to bring MQTT to MicroPython
 platforms which lack a WiFi interface.

## 1. The "resilient" driver

This is an alternative to the official driver and is targeted on the ESP8266.

It will run on ESP32 but there are known problems consequent on the
"experimental" status of the firmware. In particular the ESP32 does not recover
from WiFi outages. See [this issue](https://github.com/micropython/micropython-esp32/issues/167).

The principal features of this driver are:  
 1. Non-blocking operation for applications using uasyncio.
 2. Automatic recovery from WiFi and broker outages.
 3. True qos == 1 operation with retransmission.
 4. Improved WiFi range because of its tolerance of poor connectivity.

Its main drawback is code size. Run as frozen bytecode it uses about 50% of the
RAM on the ESP8266. On ESP32 it runs as a standard Python module with 64K of
RAM free.

It is documented [here](./README_mqtt_as.md).

## 2. MQTT for generic MicroPython targets

This comprises an ESP8266 firmware image and a MicroPython driver. The target
hardware is linked to an ESP8266 running the firmware image using a 5-wire
interface. The driver runs on the target which can then access MQTT. The driver
and hardware interface are designed to be platform agnostic: any hardware with
five GPIO pins accessible via the `machine` library should suffice.

The driver is non-blocking and is designed for applications using uasyncio.

It is documented [here](./remote_mqtt/NO_NET.md).
