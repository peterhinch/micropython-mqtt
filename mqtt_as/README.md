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
  1.8 [RP2 Pico W](./README.md#18-rp2-pico-w)  
  1.9 [Limitations](./README.md#19-limitations) Please read this.  
 2. [Getting started](./README.md#2-getting_started)  
  2.1 [Program files](./README.md#21-program-files)  
  2.2 [Installation](./README.md#22-installation)  
  2.3 [Example Usage](./README.md#23-example-usage) Using the event interface.  
  2.4 [Usage with callbacks](./README.md#24-usage-with-callbacks)  
 3. [MQTTClient class](./README.md#3-mqttclient-class)  
  3.1 [Constructor](./README.md#31-constructor) Describes the MQTT configuration dictionary.  
  3.2 [Methods](./README.md#32-methods)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.1 [connect](./README.md#321-connect)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.2 [publish](./README.md#322-publish)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.3 [subscribe](./README.md#323-subscribe)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.4 [unsubscribe](./README.md#324-unsubscribe)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.5 [isconnected](./README.md#325-isconnected)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.6 [disconnect](./README.md#326-disconnect)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.7 [close](./README.md#327-close)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.8 [broker_up](./README.md#328-broker_up)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.9 [wan_ok](./README.md#329-wan_ok)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;3.2.10 [dprint](./README.md#3210-dprint)  
  3.3 [Class Variables](./README.md#33-class-variables)  
  3.4 [Module Attribute](./README.md#34-module-attribute)  
  3.5 [Event based interface](./README.md#35-event-based-interface)  
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
  5.3 [Ultra low power consumption](./README.md#53-ultra-low-power-consumption) For ESP8266 and ESP32.  
 6. [References](./README.md#6-references)  
 7. [Connect Error Codes](./README.md#7-connect-error-codes)  
 8. [Hive MQ](./README.md#8-hive-mq) A secure, free, broker.  
 9. [The ssl_params dictionary](./README.md#9-the-ssl_params-dictionary) Plus user notes on SSL/TLS.  

## 1.1 Rationale

The official "robust" MQTT client has the following limitations.

 1. It is unable reliably to resume operation after a temporary WiFi outage.

 2. It uses blocking sockets which can cause execution to pause for arbitrary
 periods when accessing a slow broker. It can also block forever in the case of
 qos == 1 publications while it waits for a publication acknowledge which never
 arrives; this can occur on a WiFi network if an outage occurs at this point in
 the sequence.

 3. This blocking behaviour implies limited compatibility with asynchronous
 applications since pending coroutines will not be scheduled for the duration.

 4. Its support for qos == 1 is partial. It does not support retransmission in
 the event of a publication acknowledge being lost. This can occur on a WiFi
 network especially near the limit of range or in the presence of interference.
 
 5. Its partial qos == 1 support and inability reliably to resume after a WiFi
 outage places a limit on the usable WiFi range. To achieve reliable operation
 a client must be well within range of the access point (AP).

 6. As a synchronous solution it has no mechanism to support the "keepalive"
 mechanism of MQTT. This prevents the "last will" system from working. It also
 makes subscribe-only clients problematic: the broker has no means of "knowing"
 whether the client is still connected.

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

The driver requires the `asyncio` library and is intended for applications
that use it. It uses nonblocking sockets and does not block the scheduler. The
design is based on the official `umqtt` library but it has been substantially
modified for resilience and for asynchronous operation.

It is primarily intended for applications which open a link to the MQTT broker
aiming to maintaining that link indefinitely. Applications which close and
re-open the link (e.g. for power saving purposes) are subject to limitations
detailed in [Non standard applications](./README.md#5-non-standard-applications).

Hardware support: Pyboard D, ESP8266, ESP32, ESP32-S2, Pico W and Arduino Nano
RP2040 Connect.  
Firmware support: Official MicroPython firmware V1.19 or later.  
Broker support: Mosquitto is preferred for its excellent MQTT compliance.  
Protocol: The module supports a subset of MQTT revision 3.1.1.

## 1.3 Project Status

Initial development was by Peter Hinch. Thanks are due to Kevin Köck for
providing and testing a number of bugfixes and enhancements. Also to other
contributors, some mentioned below.

Note that in firmware prior to 1.21 `asyncio` was named `uasyncio`.

12 Nov 2022 V0.7.0 Provide alternative callback-free Event interface.  
2 Nov 2022 Rename `config.py` to `mqtt_local.py`, doc improvements.  
8 Aug 2022 V0.6.6 Support unsubscribe (courtesy of Kevin Köck's fork).  
11 July 2022 V0.6.5 Support RP2 Pico W  
5 July 2022 V0.6.4 Implement enhancements from Bob Veringa. Fix bug where tasks
could fail to be stopped on a brief outage. Subscription callbacks now receive
bytearrays rather than bytes objects.  
10 June 2022 Lowpower demo removed as it required an obsolete version of
`asyncio`. Improved handling of `clean_init` (issue #40).  
21 May 2022 SSL/TLS ESP8266 support contributed by @SooOverpowered: see
`tls8266.py`.  
22 Apr 2022 Support added for Arduino Nano RP2040 Connect. See note below.  
2 Aug 2021 SSL/TLS on ESP32 has now been confirmed working.
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

NINA firmware must up to date otherwise MicroPython produces error messages.
See
[this doc](https://docs.arduino.cc/tutorials/nano-rp2040-connect/rp2040-upgrading-nina-firmware).
Reading RSSI seems to break the WiFi link so should be avoided - the
`range_ex.py` demo disables this on this platform.

## 1.8 RP2 Pico W

The `mqtt_as` code should be V0.6.5 or later to avoid very slow recovery from
outages.

## 1.9 Limitations

The MQTT 3.1 protocol supports extremely long messages. On a microcontroller
message length is limited by available RAM. The actual limit will depend on the
platform and user code but it is wise to design on the basis of a maximum of
around 1KiB.

Avoid unrealistic expectations of performance: latency can be significant,
especially when using a TLS connection to a broker located on the internet.
With a non-encrypted connection to a local broker it is feasible to use one
MicroPython client to control another. I haven't measured latency but I would
guess at ~100ms. 

Some platforms - notably ESP32 - are unhelpful when dealing with gross errors
such as incorrect WiFi credentials. Initial connection will only fail after a
one minute timeout. Other platforms enable an immediate bail-out.

###### [Contents](./README.md#1-contents)

# 2. Getting started

## 2.1 Program files

### Required file

 1. `mqtt_as.py` The main module.

### Required by demo scripts

 1. `mqtt_local.py` Holds local configuration details such as WiFi credentials.

### Test/demo scripts

The first two of these demonstrate the event interface. Others use callbacks.

 1. `range.py` For WiFi range testing. Good general demo.
 2. `range_ex.py` As above but also publishes RSSI and free RAM. See code
 comments for limitations on Pico W and Arduino nano connect.
 3. `clean.py` Test/demo program using MQTT Clean Session.
 4. `unclean.py` Test/demo program with MQTT Clean Session `False`.
 5. `pubtest` Bash script illustrating publication with Mosquitto.
 6. `main.py` Example for auto-starting an application.
 7. `tls.py` Demo of SSL/TLS connection to a public broker. This runs on a
 Pyboard D. Publishes every 20s and subscribes to same topic. Connection to
 this public broker, though encrypted, is insecure because anyone can
 subscribe.
 8. `tls8266.py` SSL/TLS connection for ESP8266. Shows how to use keys and
 certificates. For obvious reasons it requires editing to run.

### Configuration

The MQTT client is configured using a dictionary. An instance named `config`
is defined in the [MQTTClient class](./README.md#3-mqttclient-class) and
populated with common default values. The user can populate this in any manner.
The approach used in the test scripts is as follows. The main `mqtt_as.py`
module instantiates `config` with typical defaults. Then `mqtt_local.py` adds
local settings common to all nodes, e.g. WiFi credentials and broker details.
Finally the application adds application specific settings like subscriptions.

In a typical project `mqtt_local.py` will be edited then deployed to all nodes.

The ESP8266 stores WiFi credentials internally: if the ESP8266 has connected to
the LAN prior to running there is no need explicitly to specify these. On other
platforms, or to have the capability of running on an ESP8266 which has not
previously connected, `mqtt_local.py` should be edited to provide them. This is
a  sample cross-platform file:
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
`esp8266/modules` in the source tree, build and deploy. Copy `mqtt_local.py` to
the filesystem for ease of making changes.

On other platforms simply copy the Python source to the filesystem (items 1 and
2 above as a minimum).

If an application is to auto-run on power-up it can be necessary to add a short
delay in main.py:
```python
import time
time.sleep(5)  # Could probably be shorter
import range  # Your application
```
This is platform dependent and gives the hardware time to initialise.

## 2.3 Example Usage

The library offers two alternative ways to handle events such as the arrival of
a message. One uses traditional callbacks. The following uses `Event` instances
and an asynchronous iterator. If a PC client publishes a message with the topic
`foo_topic` the topic and message are printed. The code periodically publishes
an incrementing count under the topic `result`.
```python
from mqtt_as import MQTTClient, config
import asyncio

# Local configuration
config['ssid'] = 'your_network_name'  # Optional on ESP8266
config['wifi_pw'] = 'your_password'
config['server'] = '192.168.0.10'  # Change to suit e.g. 'iot.eclipse.org'

async def messages(client):  # Respond to incoming messages
    async for topic, msg, retained in client.queue:
        print((topic, msg, retained))

async def up(client):  # Respond to connectivity being (re)established
    while True:
        await client.up.wait()  # Wait on an Event
        client.up.clear()
        await client.subscribe('foo_topic', 1)  # renew subscriptions

async def main(client):
    await client.connect()
    for coroutine in (up, messages):
        asyncio.create_task(coroutine(client))
    n = 0
    while True:
        await asyncio.sleep(5)
        print('publish', n)
        # If WiFi is down the following will pause for the duration.
        await client.publish('result', '{}'.format(n), qos = 1)
        n += 1

config["queue_len"] = 1  # Use event interface with default queue size
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

## 2.4 Usage with callbacks

The alternative callback-based interface may be run as follows:
```python
from mqtt_as import MQTTClient, config
import asyncio

# Local configuration
config['ssid'] = 'your_network_name'  # Optional on ESP8266
config['wifi_pw'] = 'your_password'
config['server'] = '192.168.0.10'  # Change to suit e.g. 'iot.eclipse.org'

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

MQTTClient.DEBUG = True  # Optional: print diagnostic messages
client = MQTTClient(config)
try:
    asyncio.run(main(client))
finally:
    client.close()  # Prevent LmacRxBlk:1 errors
```
As above, testing is done by running `pubtest` in one terminal and, in another,
`mosquitto_sub -h 192.168.0.10 -t result` (change the IP address to match your
broker).

###### [Contents](./README.md#1-contents)

# 3. MQTTClient class

The module provides a single class: `MQTTClient`.

## 3.1 Constructor

This takes a dictionary as argument. The default is `mqtt_as.config` which is
populated with default values listed below. A typical application imports this
and modifies selected entries as required. Entries are as follows (default
values shown in []):

### WiFi Credentials

These are required for platforms other than ESP8266 where they are optional. If
the ESP8266 has previously connected to the required LAN the chip can reconnect
automatically. If credentials are provided, an ESP8266 which has no stored
values or which has stored values which don't match any available network will
attempt to connect to the specified LAN.

'**ssid**' [`None`]  
'**wifi_pw**' [`None`]  

### MQTT parameters

'**client_id**' [auto-generated unique ID] Must be a `bytes` instance.  
'**server**' [`None`] Broker IP address (mandatory).  
'**port**' [`0`] 0 signifies default port (1883 or 8883 for SSL).  
'**user**' [`''`] MQTT credentials (if required).  
'**password**' [`''`] If a password is provided a user must also exist.  
'**keepalive**' [`60`] Period (secs) before broker regards client as having died.  
'**ping_interval**' [`0`] Period (secs) between broker pings. 0 == use default.  
'**ssl**' [`False`] If `True` use SSL.  
'**ssl_params**' [`{}`] See below.  
'**response_time**' [`10`] Time in which server is expected to respond (s). See note
below.  
'**clean_init**' [`True`] Clean Session state on initial connection.  
'**clean**' [`True`] Clean session state on reconnection.  
'**max_repubs**' [`4`] Maximum no. of republications before reconnection is
 attempted.  
'**will**' : [`None`] A list or tuple defining the last will (see below).  

### Interface definition

'**queue_len**' [`0`] If a value > 0 is passed the Event-based interface is
engaged. This replaces the callbacks defined below with a message queue and
`Event` instances. See [section 3.5](./README.md#35-event-based-interface).

### Callback based interface  

This interface is optional. It is retained for compatibility with existing
code. In new designs please consider the event based interface which replaces
callbacks with a more asyncio-friendly approach.

'**subs_cb**' [a null lambda function] Subscription callback. Runs when a message
is received whose topic matches a subscription. The callback must take three
args, `topic`, `message` and `retained`. The first two are `bytes` instances,
`retained` is a `bool`, `True` if the message is a retained message.  
'**wifi_coro**' [a null coro] A coroutine. Defines a task to run when the network
state changes. The coro receives a single `bool` arg being the network state.  
'**connect_coro**' [a null coro] A coroutine. Defines a task to run when a
connection to the broker has been established. This is typically used to
register and renew subscriptions. The coro receives a single argument, the
client instance.

### Notes

The `response_time` entry works as follows. If a read or write operation times
out, the connection is presumed dead and the reconnection process begins. If a
`qos==1` publication is not acknowledged in this period, republication will
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

`clean_init` should normally be `True`. If `False` the system will attempt to
restore a prior session on the first connection. This may result in a large
backlog of `qos==1` messages being received, for example if a client is taken
out of service for a long time. This can have the consequences described above.
See MQTT spec 3.1.2.4. This is decribe further below in
[section 4.4.2 behaviour on power up](./README.md#442-behaviour-on-power-up).

### SSL/TLS

Populating the `ssl_params` dictionary is something of a black art. Some sites
require certificates: see [this post](https://forum.micropython.org/viewtopic.php?f=18&t=11906#p65746)
for details on how to specify these. See [Hive MQ](./README.md#8-hive-mq) for
details of connecting to a secure, free broker service. This may provide hints
for connecting to other TLS brokers.

###### [Contents](./README.md#1-contents)

## 3.2 Methods

Note re data types. Messages and topics may be strings provided that all
characters have ordinal values <= 127 (Unicode single byte characters).
Otherwise the string `encode` method should be used to convert them to `bytes`
objects.

### 3.2.1 connect

Asynchronous.

Keyword only arg:  
 * `quick=False` Setting `quick=True` saves power in some battery applications.
 It does this on (re)connect by skipping the check on WiFi integrity. This check
 is intended for mobile clients that may attempt to reconnect under conditions
 of poor signal strength. In conditions of good signal strength this check may
 be skipped.  
 See [Non standard applications](./README.md#5-non-standard-applications).

Connects to the specified broker. The application should call `connect` once on
startup. If this fails (due to WiFi or the broker being unavailable) an
`OSError` will be raised: see
[Connect Error Codes](./README.md#7-connect-error-codes). Subsequent
reconnections after outages are handled automatically.

### 3.2.2 publish

Asynchronous.

If connectivity is OK the coro will complete immediately, else it will pause
until the WiFi/broker are accessible.
[Section 4.2](./README.md#42-client-publications-with-qos-1) describes qos == 1
operation.

Args:
 1. `topic` A bytes or bytearray object. Or ASCII string as described above.
 2. `msg` A bytes or bytearray object. 
 3. `retain=False` Boolean.
 4. `qos=0` Integer.

### 3.2.3 subscribe

Asynchronous.

Subscriptions should be created in the connect coroutine to ensure they are
re-established after an outage.

The coro will pause until a `SUBACK` has been received from the broker, if
necessary reconnecting to a failed network.

Args:
 1. `topic` A bytes or bytearray object. Or ASCII string as described above.
 2. `qos=0` Integer.

It is possible to subscribe to multiple topics but there can only be one
subscription callback.

### 3.2.4 unsubscribe

Asynchronous.

The coro will pause until an `UNSUBACK` has been received from the broker, if
necessary reconnecting to a failed network.

Arg:
 1. `topic` A bytes or bytearray object. Or ASCII string as described above.

If there is no subscription in place with the passed topic name the method will
complete normally. This is in accordance with MQTT spec 3.10.4 Response.

### 3.2.5 isconnected

Synchronous. No args.

Returns `True` if connectivity is OK otherwise it returns `False` and schedules
reconnection attempts.

### 3.2.6 disconnect

Asynchronous. No args.

Sends a `DISCONNECT` packet to the broker, closes socket. Disconnection
suppresses the Will (MQTT spec. 3.1.2.5). This may be done prior to a power
down or deepsleep. For restrictions on the use of this method see
[lightsleep and disconnect](./README.md#52-lightsleep-and-disconnect).

### 3.2.7 close

Synchronous. No args.

Shuts down the WiFi interface and closes the socket. Its main use is in
development to prevent ESP8266 `LmacRxBlk:1` failures if an application raises
an exception or is terminated with ctrl-C (see
[Example Usage](./README.md#23-example-usage).

### 3.2.8 broker_up

Asynchronous. No args.

Unless data was received in the last second it issues an MQTT ping and waits
for a response. If it times out (`response_time` exceeded) with no response it
returns `False` otherwise it returns `True`.

### 3.2.9 wan_ok

Asynchronous.

Returns `True` if internet connectivity is available, else `False`. It first
checks current WiFi and broker connectivity. If present, it sends a DNS query
to '8.8.8.8' and checks for a valid response.

There is a single arg `packet` which is a bytes object being the DNS query. The
default object queries the Google DNS server.

Please note that this is merely a convenience method. It is not used by the
client code and its use is entirely optional.

### 3.2.10 dprint

If the class variable `DEBUG` is true, debug messages are output via `dprint`.
This method can be redefined in a subclass, for example to log debug output to
a file. The method takes an arbitrary number of positional args as per `print`.

## 3.3 Class Variables

 1. `DEBUG` If `True` causes diagnostic messages to be printed.
 2. `REPUB_COUNT` For debug purposes. Logs the total number of republications
 with the same PID which have occurred since startup.

## 3.4 Module Attribute

 1. `VERSION` A 3-tuple of ints (major, minor, micro) e.g. (0, 5, 0).

## 3.5 Event based interface

This is invoked by setting `config["queue_len"] = N` where `N > 0`. In this
mode there are no callbacks. Incoming messages are queued and may be accessed
with an asynchronous iterator. The module reports connectivity changes by
setting bound `.up` and `.down` `Event` instances. The demos `range.py` and
`range_ex.py` use this interface. The following code fragments illustrate its use.

Reading messages:
```python
async def messages(client):
    async for topic, msg, retained in client.queue:
        print(f'Topic: "{topic.decode()}" Message: "{msg.decode()}" Retained: {retained}')
```
Handling connect events:
```python
async def up(client):  # (re)connection.
    while True:
        await client.up.wait()
        client.up.clear()
        print('We are connected to broker.')
        await client.subscribe('foo_topic', 1)  # Re-subscribe after outage
```
Optional outage handler:
```python
async def down(client):
    while True:
        await client.down.wait()  # Pause until outage
        client.down.clear()
        print('WiFi or broker is down.')
```
Initialisation with a default small queue:
```python
config["queue_len"] = 1
client = MQTTClient(config)
```
In applications where incoming messages arrive slowly and the `clean` flag is
`False`, messages will not accumulate and the queue length can be small. A
value of 1 provides a minimal queue. The queue comes into play when bursts of
messages arrive too quickly for the application to process them. This can occur
if multiple clients independently publish to the same topic: the broker may
forward them to subscribers at a high rate. Another case is when the `clean`
flag is `False` and a long wifi outage occurs: when the outage ends there may
be a large backlog of messages. Such cases may warrant a larger queue.

In the event of the queue overflowing, the oldest messages will be discarded.
This policy prioritises resilience over the `qos==1` guarantee. The bound
variable `client.queue.discards` keeps a running total of lost messages. In
development this can help determine the optimum queue length.

It is possible (though seldmom useful) to have multiple tasks waiting on
messages. These must yield control after each message to allow the others to be
scheduled. Messages will be distributed between waiting tasks in a round-robin
fashion. Multiple instances of this task may be created:
```python
async def messages(client):
    async for topic, msg, retained in client.queue:
        await asyncio.sleep(0)  # Allow other instances to be scheduled
        # handle message
```
In applications RAM is at a premium, in testing the callback-based interface
offers somewhat (~1.3KiB) lower consumption than the minimal queue case.

###### [Contents](./README.md#1-contents)

# 4. Notes

## 4.1 Connectivity

If `keepalive` is defined in the constructor call, the broker will assume that
connectivity has been lost if no messages have been received in that period.
The module attempts to keep the connection open by issuing an MQTT ping up to
four times during the keepalive interval. (It pings if the last response from
the broker was over 1/4 of the keepalive period). More frequent pings may be
desirable to reduce latency of outage detection. This may be done using the
`ping_interval` configuration option. The point here is that while WiFi
failures are detected fast, upstream failure can only be detected by an absence
of communication from the broker. With a long ping interval, the broker could
be unreachable for a long time before the client detects it and initiates a
reconnection attempt.

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

When that initial connection has been achieved, subsequent connections caused
by network outages are handled transparently to the application.

The behaviour of "clean session" should be considered in this context. If the
`clean` flag is `False` and a long power outage occurs there may be a large
backlog of messages. This can cause problems on resource constrained clients,
notably if the client has been taken out of service for a few days. This module
addresses this by enabling behaviour which differs between the power up case
and the case of a network outage.

The `clean_init` flag determines behaviour on power up, while `clean` defines
behaviour after a connectivity outage. If `clean_init` is `True` and `clean` is
`False`, on power up prior session state is discarded. The client reconnects
with `clean==False`. It reconnects similarly after connectivity outages. Hence,
after power up, subscriptions will meet the `qos==1` guarantee for messages
published during connectivity outages.

If both flags are `False` normal non-clean behaviour ensues with the potential
for substantial backlogs after long power outages.

If on power up both flags are `True` the broker will discard session state
during connectivity (and hence power) outages. This implies a loss of messages
published during connectivity outages(MQTT spec 3.1.2.4 Clean Session).

Also discussed [here](https://github.com/peterhinch/micropython-mqtt/issues/40).

###### [Contents](./README.md#1-contents)

# 5. Non standard applications

Normal operation of `mqtt_as` is based on attempting to keep the link up as
much as possible. This assures minimum latency for subscriptions but implies
power draw. The `machine` module supports two power saving modes: `lightsleep`
and `deepsleep`. Currently `asyncio` supports neither of these modes. The
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
publications which occurred during deepsleep are received and revealed by
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
lightsleep. Firstly `asyncio` does not support lightsleep on all platforms -
notably on STM where the `ticks_ms` clock (crucial to task scheduling) stops
for the duration of lightsleep.

Secondly the library has no mechanism to ensure all tasks are shut down cleanly
after issuing `.disconnect`. This calls into question any application that
issues `.disconnect` and then attempts to reconnect. This issue does not arise
with `deepsleep` because the host effectively powers down. When the sleep
ends, `asyncio` and necessary tasks start as in a power up event.

These problems have been resolved by users for specific applications with forks
of the library. Given the limitations of `asyncio` I do not plan to write a
general solution.

## 5.3 Ultra low power consumption

[This document](https://github.com/peterhinch/micropython-mqtt/tree/master/mqtt_as/esp32_gateway)
describes an MQTT client for ESP32 or ESP8266 which uses ESPNOw to communicate
with a gateway running `mqtt_as`. The client does not need to connect to WiFi
each time it wakes, saving power. The gateway can be shared between multiple
clients.

Drawbacks are the need for an always-on gateway, and the fact that only a
subset of MQTT capabilities is supported.

###### [Contents](./README.md#1-contents)

# 6. References

[mqtt introduction](http://mosquitto.org/man/mqtt-7.html)  
[mosquitto server](http://mosquitto.org/man/mosquitto-8.html)  
[mosquitto client publish](http://mosquitto.org/man/mosquitto_pub-1.html)  
[mosquitto client subscribe](http://mosquitto.org/man/mosquitto_sub-1.html)  
[MQTT 3.1.1 spec](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718048)  
[python client for PC's](https://www.eclipse.org/paho/clients/python/)  
[Unofficial MQTT FAQ](https://forum.micropython.org/viewtopic.php?f=16&t=2239)  
[List of public brokers](https://github.com/mqtt/mqtt.github.io/wiki/public_brokers)  

###### [Contents](./README.md#1-contents)

# 7. Connect Error Codes

On the initial connection attempt the broker may reject the attempt. In this
instance an `OSError` will be raised showing two numbers. The first number
should be `0x2002` which is the MQTT `CONNACK` fixed header. The second
is `CONNACK` variable header byte 2 which indicates the reason for failure as
follows:

| Value | Reason                                       |
|:------|:---------------------------------------------|
| 1     | Unacceptable protocol version.               |
| 2     | Client identifier rejected.                  |
| 3     | MQTT service unavailable.                    |
| 4     | Username or password have an invalid format. |
| 5     | Client is not authorised to connect.         |

See MQTT spec section 3.2.2.

###### [Contents](./README.md#1-contents)

# 8. Hive MQ

The [Hive MQ](https://www.hivemq.com/) site offers a free web-based broker
which is more secure than public brokers. With a public broker anyone can
detect and subscribe to your publications. Hive MQ gives you a unique broker
internet address which requires a password to access. TLS is mandatory but does
not require certificates.

A simple GitHub registration gets you:
 * The unique broker address.
 * You specify a username.
 * The website supplies a password.

Typical usage:
```python
config['user'] = 'my_username'
config['password'] = 'my_password'
broker = 'unique broker address'  # e.g long_hex_string.s2.eu.hivemq.cloud
config['server'] = broker
config['ssl'] = True
config['ssl_params'] = {"server_hostname": broker}
```
The free service is scalable (at cost) to large commercial deployments.
###### [Contents](./README.md#1-contents)

# 9. The ssl_params dictionary

The following are the allowable keys:

 * 'key'
 * 'cert'
 * 'server_side'
 * 'server_hostname'
 * 'do_handshake'
 * 'cert_reqs' mbedtls only
 * 'cadata' mbedtls only

According to [this post](https://github.com/orgs/micropython/discussions/10559#discussioncomment-4820939)
the following platforms use mbedtls:

 * esp32 port
 * pico w
 * unix port
 * stm32

See [this post](https://github.com/orgs/micropython/discussions/10801#discussioncomment-5071764)
for details of how to use client certificates with a `mosquitto` broker.

Note also that TLS with client certificates requires the cliet's clock to be
approximately correct. This can be achieved with an NTP query. If `mosquitto`
is run on a local server it also runs the NTP daemon. A high availability
option is to run the NTP query against the local server. See
[this doc](https://github.com/peterhinch/micropython-samples/blob/master/README.md#414-ntp-time),
also [the official ntptime module](https://github.com/micropython/micropython-lib/blob/master/micropython/net/ntptime/ntptime.py).

See [this link](https://github.com/JustinS-B/Mosquitto_CA_and_Certs) for
information on creating client certificates and a Bash script for doing so.
