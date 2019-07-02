# 1. MicroPython Asynchronous MQTT

MQTT Packets are passed between clients using a publish/subscribe model. They
consist of a topic and a message string. Clients subscribe to a topic and will
receive all packets published by any client under that topic.

The protocol supports three "quality of service" (qos) levels. Level 0 offers
no guarantees. Level 1 ensures that a packet is communicated to the recipient
but duplication can occur. Level 2 avoids duplication; it is not suported by
the official driver or by this module. Duplicates can readily be handled at the
application level.

###### [Main README](./README.md)

## 1.1 Rationale

The official "robust" MQTT client has the following limitations.

 1. It uses blocking sockets which can cause execution to pause for arbitrary
 periods when accessing a slow broker. It can also block forever in the case of
 qos == 1 publications while it waits for a publication acknowledge which never
 arrives; this can occur on a WiFi network if an outage occurs at this point in
 the sequence.

 This blocking behaviour implies limited compatibility with asynchronous
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

It supports qos levels 0 and 1. In the case of packets with qos == 1
retransmissions will occur until the packet has successfully been transferred.
If the WiFi fails (e.g. the device moves out out of range of the AP) the
coroutine performing the publication will pause until connectivity resumes.

The driver requires the `uasyncio` library and is intended for applications
that use it. It uses nonblocking sockets and does not block the scheduler. The
design is based on the official `umqtt` library but it has been substantially
modified for resilience and for asynchronous operation.

## 1.3 Project Status

The API has changed. Configuration is now via a dictionary, with a default
supplied in the main module.

1st April 2019
In the light of improved ESP32 firmware and the availability of the Pyboard D
the code has had minor changes to support these platforms. The API is
unchanged.

2nd July 2019
Added support for the unix port of Micropython. The unique_id must be set manually
as the unix port doesn't have the function *unique_id()* to read a chip's id.
The library assumes that the device is correctly connected to the network as the OS
will take care of the network connection. 

My attempts to test with SSL/TLS have failed. I gather TLS on nonblocking
sockets is work in progress. Feedback on this issue would be very welcome.

## 1.4 ESP8266 limitations

The module is too large to compile on the ESP8266 and should be precompiled or
preferably frozen as bytecode.
To save about 150-250 Bytes on the ESP8266 there is a minimal version `mqtt_as_minimal.py`
that works exactly like the full version but has all code not related to ESP8266 removed
as well as some functions that are not commonly used and all debug messages.

## 1.5 ESP32 issues

Firmware should be an official build dated 25th March 2019 or later. The
library has not been tested with the Loboris port which appears not to have had
any recent updates.
But it has been reported that it works correctly and is being actively used by others.

## 1.6 Dependency

The module requires `uasyncio` which may be the official or `fast_io` version;
the latter will provide no MQTT performance gain. It may be used if the user
application employs its features.

# 2. Getting started

## 2.1 Program files

 1. `mqtt_as.py` The main module.
 2. `mqtt_as_minimal.py` The main module cut down for the ESP8266 to save RAM
 3. `config.py` Stores cross-project settings.
 4. `tests` Folder containing test files for mqtt_as
    1. `clean.py` Test/demo program using MQTT Clean Session.
    2. `unclean.py` Test/demo program with MQTT Clean Session `False`.
    3. `range.py` For WiFi range testing.
    4. `pubtest` Bash script illustrating publication with Mosquitto.
    5. `main.py` Example for auto-starting an application.
    6. `ssl.py` Failed attempt to run with SSL. See note above (1.3).
 5. `remote_mqtt` Folder containing all files of mqtt for platforms without WIFI and tests
 6. `sonoff` Folder containing test files for sonoff devices
 

The ESP8266 stores WiFi credentials internally: if the ESP8266 has connected to
the LAN prior to running there is no need explicitly to specify these. On other
platforms `config.py` should be edited to provide them. A sample cross-platform
file:
```python
from micropython_mqtt_as.mqtt_as import config

config['server'] = '192.168.0.33'  # Change to suit e.g. 'iot.eclipse.org'

# Not needed for ESP8266:
config['ssid'] = 'my_WiFi_SSID'
config['wifi_pw'] = 'my_password'
```

## 2.2 Installation

The only dependency is uasyncio from the [MicroPython library](https://github.com/micropython/micropython-lib).
Many firmware builds include this by default. Otherwise ensure it is installed
on the device.

The module is too large to compile on the ESP8266. It must either be cross
compiled or (preferably) built as frozen bytecode: copy the repo to
`esp8266/modules` in the source tree, build and deploy. If your firmware 
gets too big, remove all unnecessary files or just copy the ones you need.
Minimal requirements:
- directory `micropython_mqtt_as` with these files in it:
    - `__init__.py` to make it a package
    - `mqtt_as.py` or `mqtt_as_minimal.py`
    - `config.py` for convenience, optional

On other platforms simply copy the Python source to the filesystem (listed above as minimum).

## 2.3 Example Usage

The following illustrates the library's use. If a PC client publishes a message
with the topic `foo_topic` the topic and message are printed. The code
periodically publishes an incrementing count under the topic `result`.

```python
from micropython_mqtt_as.mqtt_as import MQTTClient
from micropython_mqtt_as.config import config
import uasyncio as asyncio
from sys import platform

SERVER = '192.168.0.9'  # Change to suit e.g. 'iot.eclipse.org'

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
if platform == "linux":
    config["client_id"]="linux"

MQTTClient.DEBUG = True  # Optional: print diagnostic messages
client = MQTTClient(**config)
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

The module provides a single class: `MQTTClient`. On ESP8266 it uses the chip's
ability to automatically find, authenticate and connect to a network it has
previously encountered: the application should ensure that the device is set up
to do this.

## 3.1 Constructor

This takes all keywords found in the dictionary in `config.py` as argument. 
As a convenience you can also use this dictionary by importing it and changing
the values. You then call the constructor by `MQTTClient(**config)`, this
automatically matches the contents of the dict to the keywords of the constructor.

Entries of config dictionary are:

**WiFi Credentials**

These are required for platforms other than ESP8266: on this the device is
assumed to be connected before the user application begins. The chip reconnects
automatically.

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
args, `topic`,`message` and `retained`. These will be `bytes` instances, 
except `retained` which will be `bool` instance.  
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

### 3.2.8 wan_ok (async)

Returns `True` if internet connectivity is available, else `False`. It first
checks current WiFi and broker connectivity. If present, it sends a DNS query
to '8.8.8.8' and checks for a valid response.

### 3.2.9 unsubscribe (async)

Unsubscribes a topic, so no messages will be received anymore.

The coro will pause until a `UNSUBACK` has been received from the broker, if
necessary reconnecting to a failed network.

Args:
 1. `topic`

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
the broker was over 1/4 of the keepalive period). More frequent pings may be
desirable to reduce latency in subscribe-only applications. This may be achieved
using the `ping_interval` configuration option.

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
