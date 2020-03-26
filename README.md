# Update: This library can now only be used with the new uasyncio version that got merged into the main micropython repository!

# NOTE:
With the latest commits in the original repository by Peter Hinch, this module is now <b>USEABLE AS A DROP-IN REPLACEMENT!</b> Only change needed is how the MQTTClient is created. Look [here](./README_mqtt_as.md#23-example-usage) for an example, it is simple, the pythonic way.

# Changes to base repo of Peter Hinch

1. Sorted files and made a structure so you know which file belongs where without reading the documentation every time
2. Made repo a module to be used like 
*from micropython_mqtt_as.mqtt_as import MQTTClient
from micropython_mqtt_as.config import config*
making it possible to just clone the repo and copy it to `espXXXX/modules` also reducing file clutter in this directory.
3. ~~Removed unnecessary workarounds of official ESP32 port for ESP32 loboris fork (Feel free to report issues).~~ implemented upstream
4. Changed MQTTClient constructor initialization from using a dictionary to using keywords with default parameters. It's still possible to use the dictionary for initialization with almost no changes to existing codebase
5. ~~Made a minimal version of mqtt_as for the ESP8266 to save some RAM~~ Removed again as the removing of workarounds in the main version only got ~150B less RAM usage which is not worth the effort.
6. Added support for "unsubscribe"
7. ~~Added support for recognizing retained publications (makes change in "subs_cb" necessary as it now has to take 3 args [topic,msg,retained])~~ implemented upstream
8. All other files are updated to the new changes and are usable (e.g. tests).
9. Updated documentation to reflect all changes
10. ~~Fixes a reliability problem when having many subscribe/unsubscribe in a short time, resulting endless reconnects (see commit for changes and explanation)~~ fixed upstream, real concurrent operations possible now
11. Added support for the unix port of Micropython

Motivation for the changes:
For my project I had to adapt the library to use it on the ESP32 with loboris fork but also use it on my ESP8266 that is short on RAM all the time.
Therefore I had the following motivation for each of the above mentioned changes:
1. I don't like to walk through a mess of files not knowing which one is important or where it belongs to and I don't want to read all the documentation just to know which files belong where.
2. Like all modules this should be a directory as well, making usage easier.
3. ~~Made it work with loboris fork but did not want to use workarounds that are not needed on this fork. (Peter Hinch made it work with loboris port as well but has the workarounds still in it to be safe)~~
4. I felt that this kind of initialization is the more pythonic way of doing things but apart from that it has an important advantage on the ESP8266, removing the config dict completely uses 100-200 Bytes less, which is important on ESP8266.
5. ~~This version for the ESP8266 has all non related code (workarounds for ESP32) and also some not commonly functions removed, saving another 150-250 Bytes so that after all changes I get 250-450 Bytes more RAM which is about 2% of the available RAM.~~
6. At first I did not need that but later it became important to me so I added it
7. I made a huge workaround in a subclass to recognize retained messages instead of just supporting it directly
8. Although I do not need any other file I felt that it is important to finish the work I started and not leave half the repo unusable.
9. Wouldn't want issues because of wrong documentation or frustrated users. Have fun with it :D
10. ~~was simply needed. Sadly makes the module a little bigger~~
11. Needed that to run my projects on a Pi and it's great for testing code

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
 3. True qos == 1 operation with retransmission.
 4. Improved WiFi range because of its tolerance of poor connectivity.

It has the drawback of increased code size which is an issue on the ESP8266.
Run as frozen bytecode it uses about 50% of the RAM on the ESP8266. On ESP32
and Pyboard D it may be run as a standard Python module.

It is documented [here](./README_mqtt_as.md).

## 2. MQTT for generic MicroPython targets

This comprises an ESP8266 firmware image and a MicroPython driver. The target
hardware is linked to an ESP8266 running the firmware image using a 5-wire
interface. The driver runs on the target which can then access MQTT. The driver
and hardware interface are designed to be platform agnostic: any hardware with
five GPIO pins accessible via the `machine` library should suffice.

The driver is non-blocking and is designed for applications using uasyncio.

It is documented [here](./remote_mqtt/NO_NET.md).
