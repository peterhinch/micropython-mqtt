# 1. MicroPython Asynchronous MQTT

MQTT Packets are passed between clients using a publish/subscribe model. They
consist of a topic and a message string. Clients subscribe to a topic and will
receive all packets published by any client under that topic.

The protocol supports three "quality of service" (qos) levels. Level 0 offers
no guarantees. Level 1 ensures that a packet is communicated to the recipient
but duplication can occur. Level 2 avoids duplication; it is unsuported by the
official driver and by this module. Duplicates can readily be handled at the
application level.

###### [Main README](../README.md)

## 1.1 Rationale

The official "robust" MQTT client has the following limitations.

 1. It uses blocking sockets which can cause execution to pause for arbitrary
 periods when accessing a slow broker. It can also block forever in the case of
 qos == 1 publications while it waits for a publication acknowledge which never
 arrives; this can occur on a WiFi network if an outage occurs at this point in
 the sequence.

 This blocking behaviour implies limited compatibilty with asynchronous
 applications since pending coroutines will not be scheduled for the duration.

 2. It is unable reliably to resume operation after a temporary WiFi outage.

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

It supports qos levels 0 and 1. In the case of qos == 1 packets retransmissions
will occur until the packet has successfully been transferred. If the WiFi
fails (e.g. the device moves out out of range of the AP) the coroutine
performing the publication will pause until connectivity resumes.

The driver requires the `uasyncio` library and is intended for applications
that use it. It uses nonblocking sockets and does not block the scheduler. The
design is based on the official `umqtt` library but it has been substantially
modified for resilience and for asynchronous operation.

Testing has been performed on the ESP8266 however the code should be portable
to other MicroPython WiFi connected devices such as ESP32.

## 1.3 Limitations

The module is too large to compile on the ESP8266 and should be precompiled or
frozen as bytecode.

It is currently untested on the ESP32 and has not been tested with SSL/TLS.
Feedback on these issues would be very welcome.

# 2. Getting started

## 2.1 Program files

 1. `mqtt_as.py` The main module.
 2. `clean.py` Test/demo program using MQTT Clean Session.
 3. `unclean.py` Test/demo program with MQTT Clean Session `False`.
 4. `range.py` For WiFi range testing.
 5. `pubtest` Bash script illustrating publication with Mosquitto.
 6. `main.py` Example for auto-starting an application.

## 2.2 Installation

The only dependency is uasyncio from the [MicroPython library](https://github.com/micropython/micropython-lib).
Ensure this is installed on the device.

The module is too large to compile on the ESP8266. It must either be cross
compiled or (preferably) built as frozen bytecode: copy `mqtt_as.py` to
`esp8266/modules` in the source tree, build and deploy.

## 2.3 Example Usage

The following illustrates the library's use. If a PC client publishes a message
with the topic `foo_topic` the topic and message are printed. The code
periodically publishes an incrementing count under the topic `result`.

```python
from mqtt_as import MQTTClient
import uasyncio as asyncio
import ubinascii
from machine import unique_id

SERVER = '192.168.0.9'  # Change to suit e.g. 'iot.eclipse.org'
CLIENT_ID = ubinascii.hexlify(unique_id())  # ID unique to this device

def callback(topic, msg):
    print((topic, msg))

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

mqtt_config = {
    'subs_cb': callback,
    'connect_coro': conn_han,
    }

MQTTClient.DEBUG = True  # Optional: print diagnostic messages
client = MQTTClient(mqtt_config, CLIENT_ID, SERVER)
loop = asyncio.get_event_loop()
try:
    loop.run_until_complete(main(client))
finally:
    client.close()  # Prevent LmacRxBlk:1 errors
```

The code may be tested by running `pubtest` in one terminal and, in another,
`mosquitto_sub -h 192.168.0.9 -t result` (change the IP address to match your
broker).

# 3. MQTTClient class

The module provides a single class: `MQTTClient`. It uses the ESP8266 ability
to automatically find, authenticate and connect to a network it has previously
encountered: the application should ensure that the device is set up to do
this.

## 3.1 Constructor

This takes the following arguments defining the broker connection.  
Mandatory positional args:

 1. `mqtt_args` A dict of MQTT parameters (see below).
 2. `client_id` A `bytes` instance: MQTT client ID should be unique for broker.
 3. `server` Broker IP address.

Optional keyword only args:

 1. `port=0` Override default port (1883 or 8883 for SSL).
 2. `user=None` MQTT credentials.
 3. `password=None` If a password is provided a user must also exist.
 4. `keepalive=0` Period (secs) before broker regards client as having died.
 5. `ssl=False` Use SSL.
 6. `ssl_params={}`

### 3.1.1 The mqtt_args dict

This may contain any of the following entries and serves to modify the default
MQTT characteristics. Defaults are in [].

 1. `response_time` Time in which server is expected to respond (s). See below.
 [10]
 2. `subs_cb` Subscription callback. The callback must take two args, `topic`
 and `message`. It runs when a subscibed publication is received. [a null
 function]
 3. `wifi_coro` A coroutine. Defines a task to run when the network state
 changes. The coro receives a single boolean arg being the network state. [A
 null coro]
 4. `connect_coro` A coroutine. Defines a task to run when a connection to the
 broker has been established. This is typically used to register and renew
 subscriptions. The coro receives a single argument, the client instance. [A
 null coro]
 5. `will` A list or tuple defining the last will (see below). [`None`]
 6. `clean_init` Clean Session state on initial connection. [`True`]
 7. `clean` Clean session state on reconnection. [`True`]
 8. `max_repubs` Maximum no. of republications before reconnection is
 attempted. [4]

The `response_time` arg works as follows. If a read or write operation times
out, the connection is presumed dead and the reconnection process begins. If a
qos == 1 publication is not acknowledged in this period, republication will
occur. May need extending for slow internet connections.

The `will` argument defines a publication which the broker will issue if it
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

## 3.2 Methods

### 3.2.1 connect (async)

No args. Connects to the specified broker. The application should call
`connect` once on startup. If this fails (due to WiFi or the broker being
unavailable) an `OSError` will be raised. Subsequent reconnections after
outages are handled automatically.

### 3.2.2 publish (async)

If connectivity is OK the coro will complete immediately, else it will pause
until the WiFi/broker are accessible. Section 4.2 describes qos == 1 operation.

Args:
 1. `topic`
 2. `msg`
 3. `retain=False`
 4. `qos=0`

### 3.2.3 subscribe (async)

Subscriptions should be created in the connect coroutine to ensure they are
re-established after an outage.

The coro will pause until a `SUBACK` has been received from the broker, if
necessary reconnecting to a failed network.

Args:
 1. `topic`
 2. `qos=0`

### 3.2.4 isconnected (sync)

No args. Returns `True` if connectivity is OK otherwise it returns `False` and
schedules reconnection attempts.

### 3.2.5 disconnect (sync)

No args. Disconnects from broker, closes socket. Note that disconnection
suppresses the Will (MQTT spec. 3.1.2.5). Should only be called on termination
as there is no recovery mechanism.

### 3.2.6 close (sync)

Closes the socket. For use in development to prevent `LmacRxBlk:1` failures if
an application raises an exception or is terminated with ctrl-C (see section
2.3).

### 3.2.7 broker_up (async)

Unless data was received in the last second it issues an MQTT ping and waits
for a response. If it times out (`response_time` exceeded) with no response it
returns `False` otherwise it returns `True`.

## 3.3 Class Attributes

 1. `DEBUG` If `True` causes diagnostic messages to be printed.
 2. `REPUB_COUNT` For debug purposes. The total number of republications with
 the same PID which have occurred.

# 4. Notes

## 4.1 Connectivity

If `keepalive` is defined in the constructor call, the broker will assume that
connectivity has been lost if no messages have been received in that period.
The module attempts to keep the connection open by issuing an MQTT ping upto
four times during the keepalive interval. (It pings if the last response from
the broker was over 1/4 of the keepalive period).

If the broker times out it will issue the "last will" publication (if any).

If the client determines that connectivity has been lost it will close the
socket and periodically attempt to reconnect until it succeeds.

In the event of failing connectivity client and server publications with
qos == 0 may be lost. The behaviour of qos == 1 packets is described below.

## 4.2 Client publications with qos == 1

These behave as follows. The client waits for `response_time`. If no
acknowledgement has been received it re-publishes it, up to `MAX_REPUBS` times.
In the absence of acknowledgement the network is presumed to be down. The
client reconnects as described above. The publication is then attempted again
as a new message with a different PID. (The new PID proved necessary for
Mosquitto to recognise the message).

This effectively guarantees the reception of a qos == 1 publication, with the
proviso that the publishing coroutine will block until reception has been
acknowledged.

## 4.3 Client subscriptions with qos == 1

Where the client is subscribed to a topic with qos == 1 and a publication with
qos == 1 occurs the broker will re-publish until an acknowledgement is
received. If the broker deems that connectivity has failed it waits for the
client to reconnect. If the client was configured with `clean` set `True`,
qos == 1 messages published during the outage will be lost. Otherwise they will
be received in quick succession (which can overflow the buffer on an ESP8266
resulting in `LmacRxBlk:1` messages).

## 4.4 Application design

The library is not designed to handle concurrent publications or registration
of subscriptions. A single task should be exist for each of these activities.
If a publication queue is required this should be implemented by the
application.

The WiFi and Connect coroutines should run to completion quickly relative to
the time required to connect and disconnect from the network. Aim for 2 seonds
maximum. Alternatively the Connect coro can run indefinitely so long as it
terminates if the `isconnected()` method returns `False`.

The subscription callback will block publications and the reception of further
subscribed messages and should therefore be designed for a fast return.

# 5. References

[mqtt introduction](http://mosquitto.org/man/mqtt-7.html)  
[mosquitto server](http://mosquitto.org/man/mosquitto-8.html)  
[mosquitto client publish](http://mosquitto.org/man/mosquitto_pub-1.html)  
[mosquitto client subscribe](http://mosquitto.org/man/mosquitto_sub-1.html)  
[MQTT spec](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718048)  
[python client for PC's](https://www.eclipse.org/paho/clients/python/)  
[Unofficial MQTT FAQ](https://forum.micropython.org/viewtopic.php?f=16&t=2239)
