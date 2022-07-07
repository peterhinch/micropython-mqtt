# MicroPython Asynchronous MQTT

MQTT Packets are passed between clients using a publish/subscribe model. They
consist of a topic and a message string. Clients subscribe to a topic and will
receive all packets published by any client under that topic.

The protocol supports three "quality of service" (qos) levels. Level 0 offers
no guarantees. Level 1 ensures that a packet is communicated to the recipient
but duplication can occur. Level 2 avoids duplication; it is not supported by
the official driver or by this module. Duplicates can readily be handled at the
application level.

###### [Main README](../README.md)

# 1. Contents

 1. [Contents](./README.md#1-contents)  
  1.1 [Rationale](./README.md#11-rationale)  
  1.2 [Overview](./README.md#12-overview)  
  1.3 [Project Status](./README.md#13-project-status)  
  1.4 [ESP8266 limitations](./README.md#14-esp8266-limitations)  
  1.5 [ESP32 Issues](./README.md#15-esp32-issues)  
  1.6 [Pyboard D](./README.md#16-pyboard-d)  
  1.7 [Arduino Nano RP2040 Connect](./README.md#17-arduino-nano-rp2040-connect)  
 2. [Getting started](./README.md#2-getting_started)  
  2.1 [Program files](./README.md#21-program-files)  
  2.2 [Installation](./README.md#22-installation)  
  2.3 [Example Usage](./README.md#23-example-usage)  
 3. [MQTTClient class](./README.md#3-mqttclient-class)  
  3.1 [Constructor](./README.md#31-constructor)  
  3.2 [Methods](./README.md#32-methods)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.1 [connect](./README.md#321-connect)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.2 [publish](./README.md#322-publish)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.3 [subscribe](./README.md#323-subscribe)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.4 [isconnected](./README.md#324-isconnected)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.5 [disconnect](./README.md#325-disconnect)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.6 [close](./README.md#326-close)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.7 [broker_up](./README.md#327-broker_up)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.8 [wan_ok](./README.md#328-wan_ok)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.9 [dprint](./README.md#329-dprint)  
  3.3 [Class Variables](./README.md#33-class-variables)  
  3.4 [Module Attribute](./README.md#34-module-attribute)  
 4. [Notes](./README.md#4-notes)  
  4.1 [Connectivity](./README.md#41-connectivity)  
  4.2 [Client publications with qos == 1](./README.md#42-client-publications-with-qos-1)  
  4.3 [Client subscriptions with qos == 1](./README.md#43-client-subscriptions-with-qos-1)  
  4.4 [Application Design](./README.md#44-application-design)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;4.4.1 [Publication Timeouts](./README.md#441-publication-timeouts)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;4.4.2 [Behaviour on power up](./README.md#442-behaviour-on-power-up)  
 5. [Non standard applications](./README.md#5-non-standard-applications) Usage in specialist and micropower applications.  
  5.1 [deepsleep](./README.md#51-deepsleep)  
  5.2 [lightsleep and disconnect](./README.md#52-lightsleep-and-disconnect)  
 6. [References](./README.md#6-references)  

## 1.1 Rationale

The official "robust" MQTT client has the following limitations.

 1. It is unable reliably to resume operation after a temporary WiFi outage.

 2. It uses blocking sockets which can cause execution to pause for arbitrary
 periods when accessing a slow broker. It can also block forever in the case of
 qos == 1 publications while it waits for a publication acknowledge which never
 arrives; this can occur on a WiFi network if an outage occurs at this point in
 the sequence.

 This blocking behaviour implies limited compatibility with asynchronous
 applications since pending coroutines will not be scheduled for the duration.

 3. Its support for qos == 1 is partial. It does not support retransmission in
 the event of a publication acknowledge being lost. This can occur on a WiFi
 network especially near the limit of range or in the presence of interference.
 
 4. Its partial qos == 1 support and inability reliably to resume after a WiFi
 outage places a limit on the usable WiFi range. To achieve reliable operation
 a client must be well within range of the access point (AP).

This module aims to address these issues, at the cost of significant code size.

## 1.2 Overview

This module provides a "resilient" non-blocking MQTT driver. In this context
"resilient" means capable of reliable operation in the presence of poor WiFi
connectivity and dropouts. Clearly during a dropout or broker outage
communication is impossible but when connectivity resumes the driver recovers
transparently.

Near the limit of WiFi range communication delays may be incurred owing to
retransmissions and reconnections but nonblocking behaviour and qos == 1
integrity are maintained.

It supports qos levels 0 and 1. In the case of packets with qos == 1
retransmissions will occur until the packet has successfully been transferred.
If the WiFi fails (e.g. the device moves out out of range of the AP) the
coroutine performing the publication will pause until connectivity resumes.

The driver requires the `uasyncio` library and is intended for applications
that use it. It uses nonblocking sockets and does not block the scheduler. The
design is based on the official `umqtt` library but it has been substantially
modified for resilience and for asynchronous operation.

It is primarily intended for applications which open a link to the MQTT broker
aiming to maintainin that link indefinitely. Applications which close and
re-open the link (e.g. for power saving purposes) are subject to limitations
detailed in [Non standard applications](./README.md#5-non-standard-applications).

Hardware support: Pyboard D, ESP8266, ESP32, ESP32-S2 and Arduino Nano RP2040
Connect.  
Firmware support: Official MicroPython firmware V1.19 or later.  
Broker support: Mosquitto is preferred for its excellent MQTT compliance.  
Protocol: The module supports a subset of MQTT revision 3.1.1.

## 1.3 Project Status

Initial development was by Peter Hinch. Thanks are due to Kevin Köck for
providing and testing a number of bugfixes and enhancements. Also to other
contributors, some mentioned below.

5 July 2022 V0.6.4 Implement enhacements from Bob Veringa. Fix bug where tasks
could fail to be stopped on a brief outage. Subscription callbacks now receive
bytearrays rather than bytes objects.

10 June 2022
Lowpower demo removed as it required an obsolete version of `uasyncio`.
Improved handling of `clean_init` (issue #40).

21 May 2022
SSL/TLS ESP8266 support contributed by @SooOverpowered: see `tls8266.py`.

22 Apr 2022
Support added for Arduino Nano RP2040 Connect. See note below.

2 Aug 2021
SSL/TLS on ESP32 has now been confirmed working.
[Reference](https://github.com/peterhinch/micropython-mqtt/pull/58).

## 1.4 ESP8266 limitations

The module is too large to compile on the ESP8266 and should be precompiled or
preferably frozen as bytecode. On the reference board with `mqtt_as` frozen,
the demo script `range_ex` reports 27.4K of free RAM while running. The code
disables automatic sleep: this reduces reconnects at cost of increased power
consumption.

Notes on the Sonoff Basic R3 may be found [here](../sonoff/SONOFF.md).

## 1.5 ESP32 issues

Firmware must now be official firmware as described above. The Loboris port
has been abandoned by its author and is no longer supported.

## 1.6 Pyboard D

The library has been tested successfully with the Pyboard D SF2W and SF6W. In
testing it has clocked up eight weeks of continuous runtime and nearly 1M
messages without failure or data loss.

## 1.7 Arduino Nano RP2040 Connect

NINA firmware must be 1.4.8 or later - see
[this doc](https://docs.arduino.cc/tutorials/nano-rp2040-connect/rp2040-upgrading-nina-firmware).
Reading RSSI seems to break the WiFi link so should be avoided - the
`range_ex.py` demo disables this on this platform.

###### [Contents](./README.md#1-contents)

# 2. Getting started

## 2.1 Program files

### Required files

 1. `mqtt_as.py` The main module.
 2. `config.py` Stores cross-project settings. See below.

### Test/demo scripts

 1. `clean.py` Test/demo program using MQTT Clean Session.
 2. `unclean.py` Test/demo program with MQTT Clean Session `False`.
 3. `range.py` For WiFi range testing.
 4. `range_ex.py` As above but also publishes RSSI and free RAM. See code
 listing for limitations.
 5. `pubtest` Bash script illustrating publication with Mosquitto.
 6. `main.py` Example for auto-starting an application.
 7. `tls.py` Demo of SSL/TLS connection to a public broker. This runs on a
 Pyboard D. Publishes every 20s and subscribes to same topic. Connection to
 this public broker, though encrypted, is insecure because anyone can
 subscribe.
 8. `tls8266.py` SSL/TLS connectionfor ESP8266. Shows how to use keys and
 certificates. For obvious reasons it requires editing to run.

### config.py

This file will require editing before deploying to all nodes in a project. As
a minimum it contains broker details but usually also holds WiFi credentials.

The ESP8266 stores WiFi credentials internally: if the ESP8266 has connected to
the LAN prior to running there is no need explicitly to specify these. On other
platforms, or to have the capability of running on an ESP8266 which has not
previously connected, `config.py` should be edited to provide them. This is a
sample cross-platform file:
```python
from mqtt_as import config

config['server'] = '192.168.0.10'  # Change to suit e.g. 'iot.eclipse.org'

# Required on Pyboard D and ESP32. On ESP8266 these may be omitted (see above).
config['ssid'] = 'my_WiFi_SSID'
config['wifi_pw'] = 'my_password'
```

###### [Contents](./README.md#1-contents)

## 2.2 Installation

The module is too large to compile on the ESP8266. It must either be cross
compiled or (preferably) built as frozen bytecode: copy `mqtt_as.py` to
`esp8266/modules` in the source tree, build and deploy. Copy `config.py` to the
filesystem for convenience.

On other platforms simply copy the Python source to the filesystem (items 1 and
2 above as a minimum).

## 2.3 Example Usage

The following illustrates the library's use. If a PC client publishes a message
with the topic `foo_topic` the topic and message are printed. The code
periodically publishes an incrementing count under the topic `result`.

```python
from mqtt_as import MQTTClient, config
import uasyncio as asyncio

SERVER = '192.168.0.10'  # Change to suit e.g. 'iot.eclipse.org'

def callback(topic, msg, retained):
    print((topic, msg, retained))

async def conn_han(client):
    await client.subscribe('foo_topic', 1)

async def main(client):
    await client.connect()
    n = 0
    while True:
        await asyncio.sleep(5)
        print('publish', n)
        # If WiFi is down the following will pause for the duration.
        await client.publish('result', '{}'.format(n), qos = 1)
        n += 1

config['subs_cb'] = callback
config['connect_coro'] = conn_han
config['server'] = SERVER

MQTTClient.DEBUG = True  # Optional: print diagnostic messages
client = MQTTClient(config)
try:
    asyncio.run(main(client))
finally:
    client.close()  # Prevent LmacRxBlk:1 errors
```

The code may be tested by running `pubtest` in one terminal and, in another,
`mosquitto_sub -h 192.168.0.10 -t result` (change the IP address to match your
broker).

If an application is to auto-run on power-up it can be necessary to add a short
delay in main.py:
```python
import time
time.sleep(5)  # Could probably be shorter
import range  # Your application
```
This is platform dependent and gives the hardware time to initialise.

###### [Contents](./README.md#1-contents)

# 3. MQTTClient class

The module provides a single class: `MQTTClient`.

## 3.1 Constructor

This takes a dictionary as argument. The default is `mqtt_as.config`. Normally
an application imports this and modifies selected entries as required. Entries
are as follows (default values shown in []):

**WiFi Credentials**

These are required for platforms other than ESP8266 where they are optional. If
the ESP8266 has previously connected to the required LAN the chip can reconnect
automatically. If credentials are provided, an ESP8266 which has no stored
values or which has stored values which don't match any available network will
attempt to connect to the specified LAN.

'ssid' [`None`]  
'wifi_pw' [`None`]  

**MQTT parameters**

'client_id' [auto-generated unique ID] Must be a bytes instance.  
'server' [`None`] Broker IP address (mandatory).  
'port' [0] 0 signifies default port (1883 or 8883 for SSL).  
'user' [`''`] MQTT credentials (if required).  
'password' [`''`] If a password is provided a user must also exist.  
'keepalive' [60] Period (secs) before broker regards client as having died.  
'ping_interval' [0] Period (secs) between broker pings. 0 == use default.  
'ssl' [False] If `True` use SSL.  
'ssl_params' [{}] See [this post](https://forum.micropython.org/viewtopic.php?f=18&t=11906#p65746)
for details on how to populate this dictionary.
'response_time' [10] Time in which server is expected to respond (s). See note
below.  
'clean_init' [`True`] Clean Session state on initial connection.  
'clean' [`True`] Clean session state on reconnection.  
'max_repubs' [4] Maximum no. of republications before reconnection is
 attempted.  
'will' : [`None`] A list or tuple defining the last will (see below).

**Callbacks and coros**  

'subs_cb' [a null lambda function] Subscription callback. Runs when a message
is received whose topic matches a subscription. The callback must take three
args, `topic`, `message` and `retained`. The first two are `bytes` instances,
`retained` is a `bool`, `True` if the message is a retained message.  
'wifi_coro' [a null coro] A coroutine. Defines a task to run when the network
state changes. The coro receives a single `bool` arg being the network state.  
'connect_coro' [a null coro] A coroutine. Defines a task to run when a
connection to the broker has been established. This is typically used to
register and renew subscriptions. The coro receives a single argument, the
client instance.

**Notes**

The `response_time` entry works as follows. If a read or write operation times
out, the connection is presumed dead and the reconnection process begins. If a
qos == 1 publication is not acknowledged in this period, republication will
occur. May need extending for slow internet connections.

The `will` entry defines a publication which the broker will issue if it
determines that the connection has timed out. This is a tuple or list comprising
[`topic` (string), `msg` (string), `retain` (bool), `qos` (0 or 1)]. If the arg
is provided all elements are mandatory.

Clean sessions: If `clean` is set, messages from the server during an outage
will be lost regardless of their qos level.

If `clean` is `False` messages sent from the server with qos == 1 will be
received when connectivity resumes. This is standard MQTT behaviour (MQTT spec
section 3.1.2.4). If the outage is prolonged this can imply a substantial
backlog. On the ESP8266 this can cause buffer overflows in the Espressif WiFi
stack causing `LmacRxBlk:1` errors to appear. 
[see this doc](http://docs.micropython.org/en/latest/esp8266/esp8266/general.html).

`clean_init` should normally be `True`. If `False` the system will attempt
to restore a prior session on the first connection. This may result in a large
backlog of qos == 1 messages being received with consequences described above.
MQTT spec 3.1.2.4.

###### [Contents](./README.md#1-contents)

## 3.2 Methods

### 3.2.1 connect

Asynchronous.

Keyword only arg:  
 * `quick=False` Setting `quick=True` saves power in some battery applications.
 See [Non standard applications](./README.md#5-non-standard-applications).

Connects to the specified broker. The application should call `connect` once on
startup. If this fails (due to WiFi or the broker being unavailable) an
`OSError` will be raised. Subsequent reconnections after outages are handled
automatically.

### 3.2.2 publish

Asynchronous.

If connectivity is OK the coro will complete immediately, else it will pause
until the WiFi/broker are accessible.
[Section 4.2](./README.md#42-client-publications-with-qos-1) describes qos == 1
operation.

Args:
 1. `topic` A bytes or bytearray object.
 2. `msg` A bytes or bytearray object. 
 3. `retain=False` Boolean.
 4. `qos=0` Integer.

Messages and topics may be strings provided that all characters have ordinal
values <= 127 (Unicode single byte characters).

### 3.2.3 subscribe

Asynchronous.

Subscriptions should be created in the connect coroutine to ensure they are
re-established after an outage.

The coro will pause until a `SUBACK` has been received from the broker, if
necessary reconnecting to a failed network.

Args:
 1. `topic` A bytes or bytearray object. Or string as described above.
 2. `qos=0` Integer.

It is possible to subscribe to multiple topics but there can only be one
subscription callback.

### 3.2.4 isconnected

Synchronous. No args.

Returns `True` if connectivity is OK otherwise it returns `False` and schedules
reconnection attempts.

### 3.2.5 disconnect

Asynchronous. No args.

Sends a `DISCONNECT` packet to the broker, closes socket. Disconnection
suppresses the Will (MQTT spec. 3.1.2.5). This may be done prior to a power
down or deepsleep. For restrictions on the use of this method see
[lightsleep and disconnect](./README.md#52-lightsleep-and-disconnect).

### 3.2.6 close

Synchronous. No args.

Shuts down the WiFi interface and closes the socket. Its main use is in
development to prevent ESP8266 `LmacRxBlk:1` failures if an application raises
an exception or is terminated with ctrl-C (see
[Example Usage](./README.md#23-example-usage).

### 3.2.7 broker_up

Asynchronous. No args.

Unless data was received in the last second it issues an MQTT ping and waits
for a response. If it times out (`response_time` exceeded) with no response it
returns `False` otherwise it returns `True`.

### 3.2.8 wan_ok

Asynchronous.

Returns `True` if internet connectivity is available, else `False`. It first
checks current WiFi and broker connectivity. If present, it sends a DNS query
to '8.8.8.8' and checks for a valid response.

There is a single arg `packet` which is a bytes object being the DNS query. The
default object queries the Google DNS server.

### 3.2.9 dprint

If the class variable `DEBUG` is true, debug messages are output via `dprint`.
This method can be redefined in a subclass, for example to log debug output to
a file. The method takes an arbitrary number of positional args as per `print`.

## 3.3 Class Variables

 1. `DEBUG` If `True` causes diagnostic messages to be printed.
 2. `REPUB_COUNT` For debug purposes. Logs the total number of republications
 with the same PID which have occurred since startup.

## 3.4 Module Attribute

 1. `VERSION` A 3-tuple of ints (major, minor, micro) e.g. (0, 5, 0).

###### [Contents](./README.md#1-contents)

# 4. Notes

## 4.1 Connectivity

If `keepalive` is defined in the constructor call, the broker will assume that
connectivity has been lost if no messages have been received in that period.
The module attempts to keep the connection open by issuing an MQTT ping up to
four times during the keepalive interval. (It pings if the last response from
the broker was over 1/4 of the keepalive period). More frequent pings may be
desirable to reduce latency in subscribe-only applications. This may be done
using the `ping_interval` configuration option.

If the broker times out it will issue the "last will" publication (if any).
This will be received by other clients subscribed to the topic.

If the client determines that connectivity has been lost it will close the
socket and periodically attempt to reconnect until it succeeds.

In the event of failing connectivity client and server publications with
qos == 0 may be lost. The behaviour of qos == 1 packets is described below.

## 4.2 Client publications with qos 1

These behave as follows. The client waits for `response_time`. If no
acknowledgment has been received it re-publishes it, up to `MAX_REPUBS` times.
In the absence of acknowledgment the network is presumed to be down. The client
reconnects as described above. The publication is then attempted again as a new
message with a different PID. (The new PID proved necessary for Mosquitto to
recognise the message).

This effectively guarantees the reception of a qos == 1 publication, with the
proviso that the publishing coroutine will block until reception has been
acknowledged.

It is permissible for qos == 1 publications to run concurrently with each
paused pending acknowledgement, however this has implications for resource
constrained devices. See [Section 4.4](./README.md#44-application-design).

## 4.3 Client subscriptions with qos 1

Where the client is subscribed to a topic with qos == 1 and a publication with
qos == 1 occurs the broker will re-publish until an acknowledgment is
received. If the broker deems that connectivity has failed it waits for the
client to reconnect. If the client was configured with `clean` set `True`,
qos == 1 messages published during the outage will be lost. Otherwise they will
be received in quick succession (which can overflow the buffer on an ESP8266
resulting in `LmacRxBlk:1` messages).

## 4.4 Application design

The module allows concurrent publications and registration of subscriptions.

When using qos == 1 publications on hardware with limited resources such as
ESP8266 it is wise to avoid concurrency by implementing a single publication
task. In such cases if a publication queue is required it should be implemented
by the application.

On capable hardware it is valid to have multiple coroutines performing qos == 1
publications asynchronously, but there are implications where connectivity with
the broker is slow: an accumulation of tasks waiting on PUBACK packets implies
consumption of resources.

The WiFi and Connect coroutines should run to completion quickly relative to
the time required to connect and disconnect from the network. Aim for 2 seconds
maximum. Alternatively the Connect coro can run indefinitely so long as it
terminates if the `isconnected()` method returns `False`.

The subscription callback will block publications and the reception of further
subscribed messages and should therefore be designed for a fast return.

### 4.4.1 Publication Timeouts

A contributor (Kevin Köck) was concerned that, in the case of a connectivity
outage, a publication might be delayed to the point where it was excessively
outdated. He wanted to implement a timeout to cancel the publication if an
outage caused high latency.

Simple cancellation of a publication task is not recommended because it can
disrupt the MQTT protocol. There are several ways to address this:  
 1. Send a timestamp as part of the publication with subscribers taking
 appropriate action in the case of delayed messages.
 2. Check connectivity before publishing. This is not absolutely certain as
 connectivity might fail between the check and publication commencing.
 3. Subclass the `MQTTClient` and acquire the `self.lock` object before issuing
 the cancellation. The `self.lock` object protects a protocol sequence so that
 it cannot be disrupted by another task. This was the method successfully
 adopted and can be seen in [mqtt_as_timeout.py](./mqtt_as_timeout.py).

This was not included in the library mainly because most use cases are covered
by use of a timestamp. Other reasons are documented in the code comments.

### 4.4.2 Behaviour on power up

The library aims to handle connectivity outages transparently, however power
cycling of the client must be considered at application level. When the
application calls the client's `connect` method any failure will cause an
`OSError` to be raised. This is by design because the action to be taken is
application-dependent. A check on WiFi or broker function may be required.
There may be a need to fall back to a different network. In other applications
brief power outages may be expected: when power resumes the client will simply
reconnect. If an error occurs the application might wait for a period before
re-trying.

The behaviour of "clean session" should be considered in this context. If the
`clean` flag is `False` and a long power outage occurs there may be a large
backlog of messages. This can cause problems on resource constrained clients,
notably if the client has been taken out of service for a few days.

The `clean_init` flag aims to address the case where the application normally
runs with `clean==True`. If `clean_init=False` and `clean=True`, on power up
existing session state is discarded. Subsequently in the event of connectivity
outages subscriptions will meet the `qos==1` guarantee.

If on power up both flags are `True` the broker will forward messages pending
since the last (non-clean) session.

###### [Contents](./README.md#1-contents)

# 5. Non standard applications

Normal operation of `mqtt_as` is based on attempting to keep the link up as
much as possible. This assures minimum latency for subscriptions but implies
power draw. The `machine` module supports two power saving modes: `lightsleep`
and `deepsleep`. Currently `uasyncio` supports neither of these modes. The
notes below may be relevant to any application which deliberately closes and
re-opens the link to the broker.

## 5.1 deepsleep

Maximum power savings may be achieved by periodically connecting, handling
publications and pending subscriptions, and entering `deepsleep`. With suitable
hardware it is possible to produce an MQTT client with very low average power
consumption. This is done by keeping the application run time short and using
`machine.deepsleep` to sleep for a period. When the period expires the board
resets and `main.py` re-starts the application.

Hardware tested was the [UM Feather S2](https://feathers2.io/) available from
[Adafruit](https://www.adafruit.com/product/4769). My sample consumes only 66μA
in deepsleep mode. It has a switchable LDO regulator allowing external sensors
to be powered down when the host is in deepsleep. It also supports battery
operation via a LiPo cell with USB charging. A Pyboard D with WBUS-DIP28 has
similar properties.

The test script
[lptest_min.py](https://github.com/peterhinch/micropython-mqtt/blob/master/mqtt_as/lptest_min.py)
wakes up periodically and connects to WiFi. It publishes the value from the
onboard light sensor, and subscribes to the topic "foo_topic". Any matching
publications which occured during deepsleep are received and revealed by
flashing the blue LED.

Note that `deepsleep` disables USB. This is inconvenient in development. The
script has a test mode in which deepsleep is replaced by `time.sleep` and
`machine.soft_reset` keeping the USB link active. An alternative approach to
debugging is to use a UART with an FTDI adaptor. Such a link can survive a
deep sleep.

Each time the client goes into deepsleep it issues `.disconnect()`. This sends
an MQTT `DISCONNECT` packet to the broker suppressing the last will as per MQTT
spec para 3.1.2.5. The reasoning is that deepsleep periods are likely to be
much longer than the keepalive time. Using `.disconnect()` ensures that a last
will message is only triggered in the event of a failure such as a program
crash.

In applications which close the connection and deepsleep, power consumption may
be further reduced by setting the `quick` arg to `.connect`. On connecting or
re-connecting after an outage a check is made to ensure that WiFi connectivity
is stable. Quick connection skips this check on initial connection only, saving
several seconds. The reasoning here is that any error in initial connection
must be handled by the application. The test script sleeps for `retry` seconds
before re-trying the connection.

## 5.2 lightsleep and disconnect

The library is not designed for use in cases where the system goes into
lightsleep. Firstly `uasyncio` does not support lightsleep on all platforms -
notably on STM where the `ticks_ms` clock (crucial to task scheduling) stops
for the duration of lightsleep.

Secondly the library has no mechanism to ensure all tasks are shut down cleanly
after issuing `.disconnect`. This calls into question any application that
issues `.disconnect` and then attempts to reconnect. This issue does not arise
with `deepsleep` because the host effectively powers down. When the sleep
ends, `uasyncio` and necessary tasks start as in a power up event.

These problems have been resolved by users for specific applications with forks
of the library. Given the limitations of `uasyncio` I do not plan to write a
general solution.

###### [Contents](./README.md#1-contents)

# 6. References

[mqtt introduction](http://mosquitto.org/man/mqtt-7.html)  
[mosquitto server](http://mosquitto.org/man/mosquitto-8.html)  
[mosquitto client publish](http://mosquitto.org/man/mosquitto_pub-1.html)  
[mosquitto client subscribe](http://mosquitto.org/man/mosquitto_sub-1.html)  
[MQTT 3.1.1 spec](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718048)  
[python client for PC's](https://www.eclipse.org/paho/clients/python/)  
[Unofficial MQTT FAQ](https://forum.micropython.org/viewtopic.php?f=16&t=2239)

###### [Contents](./README.md#1-contents)
