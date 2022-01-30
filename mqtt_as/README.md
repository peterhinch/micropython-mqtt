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
  1.4 [ESP8266 Limitations](./README.md#14-esp8266-limitations)  
  1.5 [ESP32 Issues](./README.md#15-esp32-issues)  
  1.6 [Pyboard D](./README.md#16-pyboard-d)  
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
  3.3 [Class Variables](./README.md#33-class-variables)  
  3.4 [Module Attribute](./README.md#34-module-attribute)  
 4. [Notes](./README.md#4-notes)  
  4.1 [Connectivity](./README.md#41-connectivity)  
  4.2 [Client publications with qos == 1](./README.md#42-client-publications-with-qos-1)  
  4.3 [Client subscriptions with qos == 1](./README.md#43-client-subscriptions-with-qos-1)  
  4.4 [Application Design](./README.md#44-application-design)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;4.4.1 [Publication Timeouts](./README.md#441-publication-timeouts)  
 5. [Low Power Demo](./README.md#5-low-power-demo) Note: Pyboard D specific and highly experimental.  
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

Hardware support: Pyboard D, ESP8266 and ESP32.  
Firmware support: Official firmware, but see below.  
Broker support: Mosquitto is preferred for its excellent MQTT compliance.  
Protocol: Currently the module supports a subset of MQTT revision 3.1.1.

#### Firmware

A release later than V1.13 must be used.

## 1.3 Project Status

Initial development was by Peter Hinch. Thanks are due to Kevin Köck for
providing and testing a number of bugfixes and enhancements.

2 Aug 2021
SSL/TLS on ESP32 has now been confirmed working.
[Reference](https://github.com/peterhinch/micropython-mqtt/pull/58).

SSL/TLS on ESP8266 is
[not supported](https://github.com/micropython/micropython/issues/7473#issuecomment-871074210),
and it looks as if this isn't going to be fixed in the near future.

8th April 2020-10th March 2021
Adapted for new `uasyncio`.

4th Nov 2019 V0.5.0  
SSL/TLS now tested successfully on Pyboard D.  
Fix bug where ESP8266 could hang attempting to connect.  
Can now reconnect after disconnect is issued.  
Now supports concurrent qos==1 publications and subscriptions.  
**API change** The disconnect method is now asynchronous.

24th Sept 2019  
**API change:** the subscription callback requires an additional parameter for
the retained message flag.  
On ESP8266 the code disables automatic sleep: this reduces reconnects at cost
of increased power consumption.  

## 1.4 ESP8266 limitations

The module is too large to compile on the ESP8266 and should be precompiled or
preferably frozen as bytecode. On the reference board with `uasyncio` and
`mqtt_as` frozen, the demo script `range_ex` reports 21.8K of free RAM while
running.

Notes on the Sonoff Basic R3 may be found [here](../sonoff/SONOFF.md).

## 1.5 ESP32 issues

Firmware must now be official firmware as described above. The Loboris port
has been abandoned by its author and is no longer supported.

## 1.6 Pyboard D

The library has been tested successfully with the Pyboard D SF2W and SF6W. In
testing it has clocked up eight weeks of continuous runtime and nearly 1M
messages without failure or data loss.

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

### Experimental scripts

 1. `lowpower.py` Pyboard D micro-power test. See [Section 5](./README.md#5-low-power-demo).
 2. `tls8266.py` SSL/TLS connectionfor ESP8266. Fails with 
 `ssl_handshake_status: -4`.

Re TLS: It seems that the problem is due to lack of firmware support for TLS
on nonblocking sockets.

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

The only dependency is uasyncio from the [MicroPython library](https://github.com/micropython/micropython-lib).
Many firmware builds include this by default. Otherwise ensure it is installed
on the device. Installation is described in the tutorial in
[this repo](https://github.com/peterhinch/micropython-async).

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
'ssl_params' [{}]  
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
[see](http://docs.micropython.org/en/latest/esp8266/esp8266/general.html)

`clean_init` should normally be `True`. If `False` the system will attempt
to restore a prior session on the first connection. This may result in a large
backlog of qos == 1 messages being received with consequences described above.
MQTT spec 3.1.2.4.

###### [Contents](./README.md#1-contents)

## 3.2 Methods

### 3.2.1 connect

Asynchronous.

No args. Connects to the specified broker. The application should call
`connect` once on startup. If this fails (due to WiFi or the broker being
unavailable) an `OSError` will be raised. Subsequent reconnections after
outages are handled automatically.

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

### 3.2.4 isconnected

Synchronous. No args.

Returns `True` if connectivity is OK otherwise it returns `False` and schedules
reconnection attempts.

### 3.2.5 disconnect

Asynchronous. No args.

Sends a `DISCONNECT` packet to the broker, closes socket. Disconnection
suppresses the Will (MQTT spec. 3.1.2.5). This may be done prior to a power
down. After issuing `disconnect` it is possible to reconnect. Disconnection
might be done to conserve power or prior to reconnecting to a different broker
or WiFi network.

### 3.2.6 close

Synchronous. No args.

Closes the socket. For use in development to prevent `LmacRxBlk:1` failures if
an application raises an exception or is terminated with ctrl-C (see
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

###### [Contents](./README.md#1-contents)

# 5. Low power demo

This is a somewhat experimental demo and is specific to the Pyboard D.  
**NOTE** In my latest testing this ran but power consumption was 16mA. The
behavior of Pyboard D firmware seems inconsistent between releases.

The `micropower.py` script runs MQTT publications and a subscription. It
reduces current consumption to about 6mA. It requires the following from the
[async repo](https://github.com/peterhinch/micropython-async):  
 1. The `fast_io` version of `uasyncio` must be installed.
 2. `rtc_time.py` and `rtc_time_cfg.py` must be on the path and must be the
 latest version (17th Oct 2019 or later).

Verify that the `fast_io` version is installed by issuing the following at the
REPL:
```python
import uasyncio as asyncio
asyncio.version
```
The official version will throw an exception; the `fast_io` version will report
a version number (at the time of writing 0.26).

To activate power saving the USB connection to the Pyboard should be unused.
This is firstly because USB uses power, and secondly because the power saving
mechanism would disrupt USB communications. If a USB connection is provided the
demo will run, but the power saving feature will be disabled.

It is possible to acquire a REPL in this mode using an FTDI adaptor connected
to one of the Pyboard's UARTs. Use `pyb.repl_uart(uart)`.

One means of powering the Pyboard is to link the Pyboard to a USB power source
via a USB cable wired for power only. This will ensure that a USB connection is
not detected.

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
