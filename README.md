# Introduction

MQTT is an easily used networking protocol designed for IOT (internet of
things) applications. It is well suited for controlling hardware devices and
for reading sensors across a local network or the internet.

It is a means of communicating between multiple clients. A single server, also
known as a broker, manages the network. Clients may include ESP8266, ESP32 and
Pyboard D modules and other networked computers. Typical server hardware is a
Raspberry Pi or other small Linux machine which may be left running 24/7.
Public brokers
[also exist](https://github.com/mqtt/mqtt.github.io/wiki/public_brokers).

An effective PC client and server is [mosquitto](https://mosquitto.org/).

# This repository

This contains two separate projects:  
 1. A "resilient" asynchronous non-blocking MQTT driver.
 2. A means of using a cheap ESP8266 module to bring MQTT to MicroPython
 platforms which lack a WiFi interface.

## 1. The "resilient" driver

This is an alternative to the official driver. It has been tested on the
following platforms.
 1. ESP8266
 2. ESP32
 3. Pyboard D

The principal features of this driver are:  
 1. Non-blocking operation for applications using uasyncio.
 2. Automatic recovery from WiFi and broker outages.
 3. True `qos == 1` operation with retransmission.
 4. Improved WiFi range because of its tolerance of poor connectivity.

It has the drawback of increased code size which is an issue on the ESP8266.
Run as frozen bytecode it uses about 50% of the RAM on the ESP8266. On ESP32
and Pyboard D it may be run as a standard Python module.

#### [mqtt_as documentation](./mqtt_as/README.md).

## 2. MQTT for generic MicroPython targets

This comprises an ESP8266 firmware image and a MicroPython driver. The target
hardware is linked to an ESP8266 running the firmware image using a 5-wire
interface. The driver runs on the target which can then access MQTT. The driver
is non-blocking and is designed for applications using `uasyncio`.

The current version of this library is in the `bridge` directory and is
documented  
### [here](./bridge/BRIDGE.md  
It has been updated for the new version of `uasyncio`.

The old version is archived to the `pb_link` directory, although I plan to
delete this.

#### [Project archive](./pb_link/NO_NET.md).

I intend to issue a replacement of this library in the near future. Objectives
are:
 1. Compatibility with `uasyncio` V3.
 2. Improved API facilitating easy porting between platforms. In particular:
 3. Tested compatibility with the Raspberry Pi Pico.
