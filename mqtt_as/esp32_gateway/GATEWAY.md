# ESP32 MQTT Gateway

# 1. Introduction

This module provides publish and subscribe MQTT access using ESPNow. Benefits
relative to running an `mqtt_as` client are:
 1. Nodes can be designed to have extremely low power consumption.
 2. Node scripts can comprise a small amount of synchronous code.
 3. WiFi and broker outages are handled by the gateway rather than by a large
 library running on the node.

The gateway is an `mqtt_as` client running on ESP32 hardware. A good WiFi
connection provides access to an MQTT broker. One or more nodes running on ESP
hardware use ESPNow to publish and to receive MQTT messages targeted on them.

Nodes may operate in micropower mode where they spend most of the time in
deepsleep. Such operation is particularly suited to publish-only nodes;
subscription messages are subject to latency when the node is asleep. ESPNow
enables substantial power saving compared to a normal `mqtt_as` client. While
an `mqtt_as` client can be put into deepsleep between publications,
re-establishing a WiFi connection and re-connecting to the broker takes time
and consumes power. By contrast ESPNow can start very quickly after a wake from
deepsleep and communications can complete in a short period.

Where a node runs continuously, subscription messages are received promptly. A
node may have periods when it is awake and periods of sleep: the gateway's
default behaviour is to attempt to send the message immediately. If this fails
the message is queued for when the node wakes.

There are tradeoffs relative to running an `mqtt_as` client, notably in cases
where connectivity between the node and gateway is temporarily lost.
 1. If such connectivity failures are to be handled it must be done by the
 application. By contrast, in `mqtt_as` a message published with `qos==1` will
 be delivered when the outage ends.
 2. The ESPNow node supports only basic publish and subscribe aspects of MQTT,
 whereas the `mqtt_as` client adds broker directives such as last will and
 clean session.
 3. At the time of writing ESPNow is not fully characterised. It is moot
 whether the  `qos==1` guarantee is strictly honoured. There may be a chance
 that, when an ESPNow node transmits and a success status is returned, the
 message may not have been received. The gateway module provides a means to
 ensure that the `qos==1` guarantee can be met. This applies to node
 publications and requires application support.

## Under development

This module is under development. The API may change. Areas under discussion
and not currently supported:
 1. ESP8266 nodes (gateway is strictly ESP32).
 2. Support for access points with non-fixed WiFi channel numbers.
 3. ESPNow message encryption.

# 2. Files

All files should be copied to the root directory of the device.

## 2.1 Gateway

 1. `mqtt_as.py` MQTT client module.
 2. `mqtt_local.py` Customise to define WiFi credentials, broker IP address and
 gateway topic(s).
 3. `gateway.py` ESPNow gateway.
 4. `primitives` directory containing `__init__.py` and `ringbuf_queue.py`.
 5. `main.py` Ensure startup on power up.

## 2.2 Nodes

Copy the contents of the `nodes` directory to the device root. Note that
`common.py` requires customisation before copying see 
[section 4.3](./GATEWAY.md#43-gateway-setup).
 1. `common.py` Common initialisation for all nodes. Customise with ID of
 gateway and WiFi channel if this is fixed.
 2. `pubonly.py` Demo of a fixed channel micropower publish-only application.
 3. `subonly.py` As above but subscribe-only.
 4. `synctx` Example of an application which runs continuously, publishing,
 handling incoming messages and doing WiFi/broker outage detection.

# 3. Overview

If the AP channel is fixed a low power publish-only application can be simple.
The following publishes a reading once per minute from the ambient light sensor
of a [FeatherS3 board](https://esp32s3.com/):
```python
import json
from machine import deepsleep, ADC, Pin
from common import gateway, sta, espnow  # Boilerplate common to all nodes

def publish(espnow, topic, msg, retain, qos):
    message = json.dumps([topic, msg, retain, qos])
    try:
        espnow.send(gateway, message)
    except OSError:  # No connectivity with gateway.
        pass  # Try again next time we wake

adc = ADC(Pin(4), atten = ADC.ATTN_11DB)
msg = str(adc.read_u16())
publish(espnow, "light", msg, False, 0)
espnow.active(False)
sta.active(False)
deepsleep(60_000)  # When the ESP32 wakes, main.py restarts the application
```
The gateway forwards the publication to the broker which may be local or on the
internet.

For micropower nodes the gateway queues subscriptions, forwarding them to the
node in a brief time window after the node performs a publication. The gateway
subscribes to one or more topics defined in `mqtt_local.py`. A device wishing
to send a message to a node publishes to one of those topics; the message
consists of of a JSON encoded 2-list comprising the ID of the destination node
and the payload. The latter may optionally be a JSON-encoded object.

The node receives a JSON encoded 3-list comprising topic name, payload and the
retain flag.

This design means that publications are directed to a single node. It is also
possible to publish to all nodes: see [section 5.4](./GATEWAY.md#54-publication-to-multiple-nodes).

# 4. Installation

This requires the following steps. Ensure that all ESP devices to be used have
the latest daily build of firmware.

## 4.1 Access Point setup

The ESPNow protocol requires that the WiFi channel does not change. Some access
points or routers pick a channel on power up. To achieve reliable operation in
the event of a power outage there are two options:
 1. Override the AP behaviour to ensure a fixed channel.
 2. Write the node application in such a way that an outage is detected and a
 scan of channels is initiated. See [section 6.3](./GATEWAY.md#63-case-where-wifi-channel-varies).

## 4.2 mqtt-as setup

Select the hardware to become the gateway. ESP32 or S2 and S3 variants may be
employed, however I have found a standard ESP32 to suffer fewer communications
problems than an S3 with SPIRAM. Install the current build of `mqtt-as` as per
the docs and ensure it is working with your broker by running one of the demos
e.g. `range.py`. When this is complete there will be a file `mqtt_local.py` on
the device.

## 4.3 Gateway setup

Determine the identity of the gateway, to enable nodes to access it. Run
```python
from ubinascii import hexlify
from machine import unique_id
print(hexlify(unique_id()))
```
The result should be used to amend the `gateway` assignment in
`nodes/common.py` which is copied to all nodes.

Edit the file `mqtt_local.py` on the device to uncomment and amend the following
lines:
```python
config['gwtopic'] = (("gateway", 1),)
```
By default "gateway" is the topic used when other devices publish to nodes. A
topic is defined by a 2-tuple of topic name (str) and qos (int 0 or 1) used to
communicate with the broker. Multiple topics are defined by a tuple of 2-tuples.

The gateway may be started with the following `main.py` script:
```python
# Gateway startup
import time
time.sleep(4)  # Enable break-in at boot time
import gateway
gateway.run(debug=True, qlen=10, lpmode=True)
```
Run args:
 1. `debug` Prints progress and RAM usage messages.
 2. `qlen` Defines the size (for each node) of the incoming MQTT message queue.
 3. `lpmode` If `True` the gateway makes no attempt to send messages to nodes
 unless they have just transmitted and are known to be ready to receive. Avoids
 spurious message transmission if all nodes are mainly in `deepsleep`.

## 4.4 Testing

On another ESP32, determine and note its unique ID:
```python
from ubinascii import hexlify
from machine import unique_id
print(hexlify(unique_id()))
```
Ensure that the file `nodes/common.py` has the correct gateway ID and WiFi
channel number. Copy the files `common.py` and `synctx.py` to the device. With
the gateway running, run
```python
import synctx
```
It should report publications at three second intervals. On a PC run the
following (changing the IP address to that of the broker):
```bash
$ mosquitto_sub -h 192.168.0.10 -t shed
```
This should receive the publications. To publish to the device run this, 
changing the IP address and the destination device ID:
```bash
$ mosquitto_pub -h 192.168.0.10 -t gateway -m '["70041dad8f14", "hello"]' -q 1
```
# 5. Detailed Description

Nodes can publish to any topic. If there is an outage of the WiFi AP or the
broker a response is sent enabling the application to respond as required. It
is possible to request an acknowledge to every message sent. This can be used
to ensure adherence to the `qos==1` guarantee.

The gateway subscribes to one or more topic. When a device publishes to one of
those topics, the gateway checks the format of the message. Unless the message
has a specific format, it is ignored. Correctly formatted messages are
forwarded either to an individual node or to all nodes.

If a node is awake and `lpmode` in `main.py` is `False` the message is
forwarded immediately. If communications fail, the message is queued and will
be sent the next time the node communicates with the gateway. This is the
normal means of operation for micropower nodes.

## 5.1 Publications from a node

Each node sends the gateway a message comprising a json-encoded 4-list. 
Elements are:
 1. `topic:str`
 2. `message:str`
 3. `retain:bool`
 4. `qos:int`

These are as per `mqtt_as` documentation with the exception that bit 2 of `qos`
may be set: in this case the gateway will respond with an acknowledge. This
enables the design of nodes which re-transmit lost ESPNow messages. The
acknowledge takes the form of a subscribed message having topic and message
fields being `"ACK"` (see below).

## 5.2 Publications to a node

### 5.3.1 Gateway setup

A device sends a message to a node by publishing a specially formatted message.
The topic must be one to which the gateway has subscribed. The gateway
subscribes to a set of topics defined as a tuple in the file `mqtt_local.py`. A
topic is defined as a 2-tuple with the following elements:
 1. `topic_name:str`
 2. `qos:int` This is the qos to use in communication with the broker. The
 default is the single topic "gateway" with qos of 1. It is defined as follows
 in `mqtt_local.py`:
```python
config["gwtopic"] = (("gateway", 1),)  # Can add further topics to outer tuple
```
Publications to these topics should comprise a JSON-encoded 2-list whose
elements are:
 1. ID of destination node.
 2. Actual text of message (which may itself be a JSON-encoded object).

A typical publication looks like
```bash
$ mosquitto_pub -h 192.168.0.10 -t gateway -m '["70041dad8f14", "hello"]' -q 1
```
Where `192.168.0.10` is the IP address of the broker, `gateway` is the gateway
topic, `"70041dad8f14"` is the ID of the destination node, and `"hello"` is the
MQTT message.

### 5.3.2 Node setup

All nodes are set up to receive ESPNow messages via `common.py`. When a device
publishes to one of the gateway topics, and the message is either targeted on
the node or is in a wildcard format, the gateway forwards an ESPNow message to
the node. A normal message is a JSON-encoded 3-list comprising:
 1. `topic:str`
 2. `message:str` This may itself be JSON-encoded for complex objects.
 3. `retained:bool`
`"OUT"` and `"ACK"` messages are 2-lists lacking the `retained` element.

## 5.3 Broker/WiFi outages

If an outage occurs the gateway will respond to a publish attempt with a
subscribe message `["OUT", "OUT"]`. The published message will be lost. The
application may want to re-try after a delay.

## 5.4 Publication to multiple nodes

There are two ways to do this. Both will send a message to all nodes that have
either published or been the target of a message from another MQTT client. One
method uses the ESPNow broadcast address:
```bash
$ mosquitto_pub -h 192.168.0.10 -t gateway -m '["FFFFFFFFFFFF", "hello"]' -q 1
```
the other uses an `"all"` address:
```bash
$ mosquitto_pub -h 192.168.0.10 -t gateway -m '["all", "hello"]' -q 1
```
In both cases the topic must be one of those defined in `mqtt_local.py`.

The broadcast approach will cause the gateway to send a message to any ESP32
unit that is in range. ESPNow offers no feedback on whether a broadcast
transmission succeeded. The gateway makes two attempts to send the message:
when it is received and after the node next publishes. If the node is awake
and listening when the message is sent, it will receive it again after it next
publishes.

The `"all"` destination overcomes those limitations using normal transmissions
employing the ESPNow feedback to minimise the risk of duplicates. Transmission
is restricted to nodes "known to" the gateway: either because they have
published previously or because the node has already been sent a message.

## 5.5 Message integrity

Radio communications suffer from three potential issues:
 1. Corrupted messages.
 2. Duplicate messages.
 3. Missing messages.

In ESPNow Corrupted messages never seem to occur. The TCP/IP protocol ensures
they are not a problem for MQTT.

Dupes can occur for various reasons, including the limitations of MQTT qos==1.
ESPNow transmission uses a handshake to verify successful transmission. This
can be pessimistic, reporting failure when success has occurred. In this
situation the gateway will re-transmit, causing a dupe. There is also the issue
of broadcast messages to clients that are awake, as discussed above. If dupes
are an issue a message ID should be used to enable the application to discard
them.

At MQTT level missing messages should never occur if qos==1 is used. ESPNow has
a handshake which, in conjunction with the gateway design, should avoid missing
messages from the node. For cast-iron certainty, node publications can request
an acknowledge enabling the application to retransmit. Incoming node messages
have no such mechanism and rely on the ESPNow handshake. I haven't yet
established if the handshake can be considered "perfect" in preventing missed
messages.

# 6. Node application design

## 6.1 Micropower Nodes

In general a node is designed to start, publish, optionally handle subscription
messages, deepsleep for a period, and quit. The `main.py` script restarts it;
consequently no state is retained between runs. To minimise power consumption
code should run as quickly as possible: if possible looping constructs should
be avoided. Code is typically synchronous: `uasyncio` has no support for sleep.

Messages received by the gateway and targeted on a node are forwarded when the
node wakes up and performs a publication. Any messages sent since the last
wakeup will rapidly be received in the order in which they were created. If
more messages were sent than can fit in the queue, the oldest messages will be
lost.

When debugging an application it is often best to start out with `time.sleep()`
calls as this keeps the USB interface active. When the basic design is proven,
`sleep` may be replaced with `deepsleep`. Applications which deepsleep may be
debugged using a UART and an FTDI adapter.

An example of a micropower publish-only application is `pubonly.py` and is
listed in [section 3](./GATEWAY.md#3-overview). A subscribe-only application
is `subonly.py`, listed below. Note that because a node is deaf when sleeping,
incoming messages are only received after a publication. A dummy publication
is used to provoke the gateway into sending any pending messages.
```python
import json
from machine import deepsleep, Pin
from neopixel import NeoPixel
from common import gateway, sta, espnow
from time import sleep_ms

np = NeoPixel(Pin(40), 1)  # 1 LED
colors = {"red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255)}

breakout = Pin(8, Pin.IN, Pin.PULL_UP)
if not breakout():  # Debug exit to REPL after boot
    import sys
    sys.exit()

def trigger(espnow):
    message = json.dumps(["dummy", "dummy", False, 0])
    try:
        espnow.send(gateway, message)
    except OSError:  # Radio communications with gateway down.
        return
    msg = None
    while True:  # Discard all but last pending message
        mac, content = espnow.recv(200)
        if mac is None:  # Timeout: no pending message from gateway
            break
        msg = content
    try:
        message = json.loads(msg)
    except (ValueError, TypeError):
        return  # No message or bad message
    np[0] = colors[message[1]]
    np.write()
    sleep_ms(500)  # Not micropower but let user see LED

trigger(espnow)
espnow.active(False)
sta.active(False)
deepsleep(3_000)
```
This enables an MQTT client to flash the LED on a UM FeatherS3 board with a
message like
```bash
mosquitto_pub -h 192.168.0.10 -t gateway -m '["f412fa420cd4", "red"]' -q 1
```
The LED flashing is not exactly micropower, but it illustrates the concept.
The node requests data by publishing. If the application has no need to publish,
a dummy message may be sent.

## 6.2 Other nodes

If power consumption is not a concern a node may be kept running continuously.
The application can use synchronous or asynchronous code and can expect to
receive subscribed messages promptly. A continuously running publish-only
application should probably check for incoming messages (such as `OUT`) to
remove them from the ESPNow buffer.

A continuously running application may be genuinely subscribe-only provided
that the gateway is run with `lpmode=False`: the connection is full-duplex
with messages arriving with minimal latency.

## 6.3 Case where WiFi channel varies

**TODO** Consult with @glenn20

# 7. MQTT - the finer points

The gateway communicates with the broker via an `mqtt_as` client. This supports
the last will and clean session mechanisms which are instructions to the broker
on how to behave in response to client outages. To enable the broker to detect
outages the client sends messages to the broker at regular intervals.

The broker has no concept of nodes attached to a client. Thus a `will` entry in
the `config` dictionary applies to the gateway, not to any of its nodes. Adding
node level mechanisms would require the gateway to act as a mini-broker. It
would complicate node scripts and would conflict with micropower operation (by
requiring regular ping messages). It would also require node scripts to be
asynchronous.

I have no plan to implement these.

When a node publishes a message the `retain` flag works normally: the broker
retains the message for future subscribers if `qos==1`. See the MQTT spec.

# 8. ESP8266 Nodes

Currently these are unsupported. From the docs:

> Receiving messages from an ESP8266 device: Strangely, an ESP32 device connected
to a wifi network using method 1 or 2 above, will receive ESPNow messages sent to
the STA_IF MAC address from another ESP32 device, but will reject messages from
an ESP8266 device!!!. To receive messages from an ESP8266 device, the AP_IF
interface must be set to active(True) and messages must be sent to the AP_IF MAC
address.

It seems a bad idea to force the gateway to run an access point interface
and it complicates the gateway design to concurrently support two different
`espnow` interfaces. There is also a question over whether the gateway's AP
interface will track the channel number of its station interface which is set
when the station interface connects to the system AP.

Further there is a question whether this behaviour is a feature or a bug -
in which case it will be fixed in the ESP IDF.

Comments welcome.

# Appendix 1 Power saving

Where a target has limited power available there are measures which can be
taken to reduce the energy consumed each time it wakes from deepsleep.

When a target wakes from deepsleep the MicroPython runtime starts. Execution
of Python user code starts with `main.py`. Where code imports Python modules
these are compiled to bytecode which is executed. Running the compiler takes
time and consumes power. Compilation can be eliminated by precompiling files.
At runtime these files need to be retrieved from the filesystem and put in
RAM. This stage can be removed by using frozen bytecode with the code being
directly executed from flash.

See [this repo](https://github.com/glenn20/upy-esp32-experiments) from @glenn20
for a much more detailed exposition including ways to radically reduce energy
used on boot.
