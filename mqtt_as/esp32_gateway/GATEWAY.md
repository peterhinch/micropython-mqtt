# ESP32 MQTT Gateway

# 1. Introduction

This module provides publish and subscribe MQTT access using ESPNow. Benefits
relative to running an `mqtt_as` client are:
 1. Nodes can be designed to have extremely low power consumption.
 2. Node scripts can comprise a small amount of synchronous code. On ESP8266
 the MQTT node interface is much smaller than a full `mqtt_as` client.
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
default behaviour is to queue MQTT messages for when the node wakes. This may
be changed such that the gateway tries to send the message immediately, only
queueing it on failure.

There are tradeoffs relative to running an `mqtt_as` client, notably in cases
where connectivity between the node and gateway is temporarily lost.
 1. If such connectivity failures are to be handled it must be done by the
 application. By contrast, in `mqtt_as` a message published with `qos==1` will
 be delivered when the outage ends.
 2. The ESPNow node supports only basic publish and subscribe MQTT operations,
 whereas the `mqtt_as` client adds broker directives such as last will and
 clean session.
 3. At the time of writing ESPNow is not fully characterised. It is moot
 whether the  `qos==1` guarantee is strictly honoured. There may be a chance
 that, when an ESPNow node transmits and a success status is returned, the
 message may not have been received. The gateway module provides a means to
 ensure that, in the case of node publications, the `qos==1` guarantee can be
 met. This requires application support.

## Under development

This module is under development. The API may change. Areas under discussion
and not currently supported:
 1. Support for access points with non-fixed WiFi channel numbers.
 2. ESPNow message encryption.
 3. Gateway status reporting.

# 2. Files

## 2.1 Gateway

This is normally installed with `mip`. Files are listed for reference.
 1. `mqtt_as.py` MQTT client module.
 2. `mqtt_local.py` Customise to define WiFi credentials and broker IP address.
 3. `gateway.py` ESPNow gateway.
 4. `gwconfig.py` Configuration file for gateway.
 5. `primitives` directory containing `__init__.py` and `ringbuf_queue.py`.

## 2.2 Nodes

The only required file is `common.py` which should be copied from the `nodes`
directory to the device root. Note that this file requires customisation before
copying to identify the gateway and WiFi channel. See [section 4.3](./GATEWAY.md#43-gateway-setup).

The following demos are optional:
 1. `pubonly.py` Demo of a fixed channel micropower publish-only application.
 2. `subonly.py` As above but subscribe-only.
 3. `synctx` Example of an application which runs continuously, publishing,
 handling incoming messages and doing WiFi/broker outage detection.

# 3. Overview

If the AP channel is fixed, a low power publish-only application can be simple.
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
subscribes to one topic defined in `gwconfig.py`: publications to that topic
(default "allnodes") are forwarded to all nodes. A node can subscribe to
additional topics. This enables external devices to publish to any subset of
the nodes.

The node receives a JSON encoded 3-list comprising topic name, payload and the
retain flag. See the demo `subonly.py` for an example where a node subscribes
to a topic and goes to sleep. On waking, pending messages are received.

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

## 4.2 Gateway installation

Select the hardware to become the gateway. ESP32 or S2 and S3 variants may be
employed, however I have found a standard ESP32 to suffer fewer communications
problems than an S3 with SPIRAM. 

On the gateway device, connect to WiFi and install with
```python
import mip
mip.install("github:peterhinch/micropython-mqtt/mqtt_as/esp32_gateway")
```
Edit the file `lib/gateway/mqtt_local.py` on the device to include the correct
WiFi credentials and broker IP address. This file is as follows:
```python
from sys import platform, implementation
from .mqtt_as import config

# Entries must be edited for local conditions
config['server'] = '192.168.0.10'  # Broker
#  config['server'] = 'test.mosquitto.org'

config['ssid'] = 'your_network_name'
config['wifi_pw'] = 'your_password'
```
### Gateway test

The following tests verify communication between the gateway and the broker.
Assuming that the broker is on 192.168.0.10, open a terminal and issue
```bash
$ mosquitto_sub -h 192.168.0.10 -t gw_status
```
Start the gateway by issuing the import at the device REPL - the following
output should ensue:
```python
>>> import gateway.gateway
ESPNow ID: b'70041dad8f15'
Checking WiFi integrity.
Got reliable connection
Connecting to broker.
Connected to broker.
Gateway b'70041dad8f15' connected to broker 192.168.0.10.
```
The terminal running `mosquitto_sub` should show
```bash
12/7/2023 16:52:13 Gateway b'70041dad8f15' connected to broker 192.168.0.10.
```
A further check is to open another terminal window and issue
```bash
$ mosquitto_pub -h 192.168.0.10 -t gw_query -m "hello"
```
`mosquitto_sub` should produce a response. Currently this is
```bash
12/7/2023 16:52:58 Status request not yet implemented
```
but any response proves that the gateway is handling publication and
subscription. Keep a record of the gateway ID (`b'70041dad8f15'` in the above
example). This is its MAC address in hex format and is required by the nodes.

## 4.3 Node setup

The following two lines in `nodes/common.py` should be edited to reflect the
gateway ID and the WiFi channel number. The latter can be set to `None` to scan
for channels, but this option currently does not work.
```python
gateway = unhexlify(b'2462abe6b0b5')
channel = 3  # Router channel or None to scan
```
Note that the gateway ID is dependent on the `"use_ap_if"` entry in
`gwconfig.py`.

The file `common.py` should be copied to the root of all nodes, along with test
script `synctx.py`.

## 4.4 Node Testing

With the gateway running, on a node with `common.py` and `synctx.py`, run
```python
import synctx
```
It should report publications at three second intervals. On a PC run the
following (changing the IP address to that of the broker):
```bash
$ mosquitto_sub -h 192.168.0.10 -t shed
```
This should receive the publications. To publish to the device run this, 
changing the IP address:
```bash
$ mosquitto_pub -h 192.168.0.10 -t allnodes -m "hello" -q 1
```
# 5. Detailed Description

Nodes can publish to any topic. If there is an outage of the WiFi AP or the
broker a response is sent enabling the application to respond as required. It
is possible to request an acknowledge to every message sent. This can be used
to ensure adherence to the `qos==1` guarantee.

The gateway subscribes to a default topic plus others created by nodes. When an
external device publishes to one of those topics, the gateway checks the format
of the message. Unless the message has a specific format, it is ignored.
Correctly formatted messages are forwarded either to an individual node or to
all nodes.

If a node is awake and `lpmode` in `gwconfig.py` is `False` the message is
forwarded immediately. If communications fail, the message is queued and will
be sent the next time the node communicates with the gateway. This is the
normal means of operation for micropower nodes.

## 5.1 Gateway configuration

The file `gwconfig.py` instantiates a `defaultdict` with entries defining the
mode of operation of the gateway. These have default values so the file may not
need to be edited for initial testing. Keys and defaults are as follows:
```python
PubIn = namedtuple('PubIn', 'topic qos')  # Publication to gateway/nodes from outside
PubOut = namedtuple('PubOut', 'topic retain qos')  # Publication by gateway

gwcfg = defaultdict(lambda : None)
gwcfg["debug"] = True  # Print debug info. Also causes more status messages to be published.
gwcfg["qlen"] = 10  # No. of messages to queue (for each node).
# If queue overruns (e.g. because node is asleep), oldest messages will be lost.
gwcfg["lpmode"] = True  # Set True if all nodes are micropower: messages are queued
# and only forwarded to the node after it has published.
# If False the gateway will attempt to send the message on receipt, only queuing
# it on failure.
gwcfg["use_ap_if"] = True  # Enable ESP8266 nodes by using AP interface
# This has the drawback of visibility. If all nodes are ESP32 this may be set False
# enebling station mode to be used. Note that this affects the gateway ID.
gwcfg["pub_all"] = PubIn("allnodes", 1)  # Publish to all nodes

# Optional keys
gwcfg["errors"] = PubOut("gw_errors", False, 1)  # Gateway publishes any errors.
gwcfg["status"] = PubOut("gw_status", False, 0)  # Destination for status reports.
gwcfg["statreq"] = PubIn("gw_query", 0)  # Status request (not yet implemented)
```
`PubIn` objects refer to topics to which the gateway will respond. `PubOut`
topics are those to which the gateway may publish. If an error occurs the
gateway will publish it to the topic defined in "errors". If "debug" is `True`
it will also print it.

Gateway publications may be prevented by omitting the optional `PubOut` key. 

## 5.2 Publications from a node

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

## 5.3 Publications to a node

A device sends a message to a node by publishing a specially formatted message.
The topic must be one to which the gateway has subscribed. The gateway
subscribes to a default topic defined as a tuple in the file `mqtt_local.py`. A
topic is defined as a 2-tuple with the following elements:
 1. `topic_name:str`
 2. `qos:int` This is the qos to use in communication with the broker. The
 default is the topic "gateway" with qos of 1. It is defined as follows in
 `mqtt_local.py`:
```python
config["gwtopic"] = ("gateway", 1)
```
A typical publication looks like
```bash
$ mosquitto_pub -h 192.168.0.10 -t allnodes -m "hello" -q 1
```
Where `192.168.0.10` is the IP address of the broker, `allnodes` is the gateway
topic, and `"hello"` is the MQTT message. The message can optionally be a JSON
encoded object.

### 5.3.2 Node setup

All nodes are set up to receive ESPNow messages via `common.py`. When a device
publishes to a topic to which a node is subscribed, the gateway forwards an
ESPNow message to the node. All nodes are subscribed to the default topic.

A normal message is a JSON-encoded 3-list comprising:
 1. `topic:str`
 2. `message:str` This may itself be JSON-encoded for complex objects.
 3. `retained:bool`
`"OUT"` and `"ACK"` messages are 2-lists lacking the `retained` element.

## 5.4 Broker/WiFi outages

If an outage occurs the gateway will respond to a publish attempt with a
subscribe message `["OUT", "OUT"]`. The published message will be lost. The
application may want to re-try after a delay.

The gateway will publish status messages indicating connection state.

## 5.5 Publication to multiple nodes

This is done by publishing to the default topic as defined in `gwconfig.py`.
The message will be forwarded to all nodes which have communicated with the
gateway. With the default topic "allnodes":
```bash
$ mosquitto_pub -h 192.168.0.10 -t allnodes -m "hello" -q 1
```
## 5.6 Subscriptions

If a node wishes to subscribe to a topic, the `subscribe` method may be used.
```python
from common import gateway, sta, espnow, subscribe
subscribe("foo_topic", 1)  # Subscribe with qos==1
```
If another node has already subscribed to this topic, the node will be added to
the set of subscribed nodes. If no other node has subscribed to this topic, the
gateway will subscribe to the broker and will create a record identifying the
topic and the node so that messages are routed to that node.

## 5.6 Message integrity

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
from common import gateway, sta, espnow, subscribe
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
    except OSError:  #   # Radio communications with gateway down.
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

subscribe("foo_topic", 1)
trigger(espnow)
espnow.active(False)
sta.active(False)
deepsleep(3_000)
# Now effectively does a hard reset
```
This enables an MQTT client to flash the LED on a UM FeatherS3 board with a
message like
```bash
mosquitto_pub -h 192.168.0.10 -t allnodes -m "red" -q 1
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

This is addressed by, in `common.py`, setting `channel = None`. This prompts
the gateway to scan for channels on startup. A `common.scan()` method is
available which enables the application to re-scan if communications fail.

Currently this **does not work**.

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
