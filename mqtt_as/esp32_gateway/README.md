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

![Image](./images/block_diagram.png)

Nodes may run synchronous or asynchronous code. They can run continuously or
operate in micropower mode where they spend most of the time in deepsleep. 
ESPNow enables substantial power saving compared to a normal `mqtt_as` client.
While an `mqtt_as` client can be put into deepsleep between publications,
re-establishing a WiFi connection and re-connecting to the broker takes time
and consumes power. By contrast ESPNow can start very quickly after a wake
from deepsleep and communications can complete quickly.

Continuously running asynchronous nodes can receive subscription messages with
low latency. Clearly this is not the case for micropower nodes which can only
receive messages when they wake: the gateway queues messages for when the node
wakes.

## 1.1 Tradeoffs relative to mqtt_as

There are tradeoffs relative to running an `mqtt_as` client. The ESPNow node
supports only basic publish and subscribe MQTT operations, whereas the
`mqtt_as` client adds broker directives such as last will and clean session.

The `qos==1` guarantee is honoured for publications from the node. Messages to
the node are dependent on the reliability of the ESPNow interface. In testing
no failures have been observed but it is not possible to provide an absolute
guarantee that a `qos==1` message will be received.

Handling of broker outages and WiFi channel changes is automatic in an
`mqtt_as` client. Applications running on nodes need application support to
re-connect after an outage, however this is very simple.

On the plus side code is small and can be run on an ESP8266 without special
precautions with over 25K of free RAM. Achieving long term battery opertaion is
easy.

## 1.2 Hardware

The gateway requires an ESP32, preferably a standard ESP32 with or without
SPIRAM. Nodes may be ESP32, ESP8266, or ESP32 variants. However there are
caveats around the ESP32-S3 - see
[this message](https://github.com/orgs/micropython/discussions/12017#discussioncomment-6465361)
with recommendations from a hardware manufacturer.

## Under development

This module is under development. Code should be considered beta quality.

# 2. Overview

## 2.1 Micropower publish-only applications

A micropower publish-only application can be simple. The following publishes a
reading once per minute from the ambient light sensor of a
[FeatherS3 board](https://esp32s3.com/):
```python
from machine import deepsleep, ADC, Pin
import time
from .link import Link
from .link_setup import gateway, channel, credentials  # Args common to all nodes
gwlink = Link(gateway, channel, credentials)
# In micropower mode need a means of getting back to the REPL
# Check the pin number for your harwdware!
gwlink.breakout(Pin(8, Pin.IN, Pin.PULL_UP))  # Pull down for debug exit to REPL

adc = ADC(Pin(4), atten = ADC.ATTN_11DB)
msg = str(adc.read_u16())
gwlink.publish("light", msg, False, 0)
gwlink.close()
deepsleep(60_000)  # main.py runs the app again when deepsleep ends.
```
The gateway forwards the publication to the broker which may be local or on the
internet.

## 2.2 Micropower subscribe-only applications

The following script wakes every 10s, receives any messages published to
"foo_topic" or "allnodes" and re-publishes them to "shed".
```python
from machine import deepsleep, Pin
from .link import Link
from .link_setup import gateway, channel, credentials  # Args common to all nodes
gwlink = Link(gateway, channel, credentials)

# In micropower mode need a means of getting back to the REPL
# Check the pin number for your harwdware!
#gwlink.breakout(Pin(15, Pin.IN, Pin.PULL_UP))  # Pull down for REPL.

def echo(topic, message, retained):
    gwlink.publish("shed", message)


gwlink.subscribe("foo_topic", 1)
gwlink.get(echo)  # Get any pending messages
gwlink.close()
deepsleep(10_000)
# Now effectively does a hard reset: main.py restarts the application.
```

The gateway queues subscriptions, forwarding them to the node . The gateway
subscribes to one topic defined in `gwconfig.py`: publications to that topic
(default "allnodes") are forwarded to all nodes. A node can subscribe to
additional topics. This enables external devices to publish to any subset of
the nodes.

The node receives a JSON encoded 3-list comprising topic name, payload and the
retain flag. See the demo `subonly.py` for an example where a node subscribes
to a topic and goes to sleep. On waking, pending messages are received.

# 3. Quick start guide

This requires the following steps. Ensure that all ESP devices to be used have
the latest daily build of firmware.

## 3.1 Access Point setup

The ESPNow protocol requires that the WiFi channel does not change. Some access
points or routers pick a channel on power up or may change channel in response
to varying radio conditions. Ideally the AP should be set to use a fixed
channel. This enables a rapid response to an outage and minimises power
consumption of micropower nodes, which otherwise have to reconnect each time
they wake. While this is automatic, it uses power.

## 3.2 Gateway installation

On the gateway device, connect to WiFi and install with
```python
import mip
mip.install("github:peterhinch/micropython-mqtt/mqtt_as/esp32_gateway")
```
Edit the file `lib/gateway/mqtt_local.py` on the device to include the correct
WiFi credentials and broker IP address. This file is as follows:
```python
from .mqtt_as import config

# Entries must be edited for local conditions
config['server'] = '192.168.0.10'  # Broker
#  config['server'] = 'test.mosquitto.org'

config['ssid'] = 'your_network_name'
config['wifi_pw'] = 'your_password'
```
## 3.3 Gateway test

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

## 3.4 Synchronous node installation and setup

On the node device, connect to WiFi and install with
```python
import mip
mip.install("github:peterhinch/micropython-mqtt/mqtt_as/esp32_gateway/nodes")
```
Node configuration is done by editing the file `lib/nodes/link_setup.py`. This
creates the following variables:
 1. `gateway` MAC address of the gateway as a 12 character string.
 2. `debug` `True` to output debug messages.
 3. `channel` Set to channel number if fixed, else `None`.
 4. `credentials` Set to `None` if channel is fixed else `('ssid', 'password')`.

The following edit is required in all cases:
```python
gateway = bytes.fromhex(b'2462abe6b0b5')  # Your gateway MAC
```
If the AP channel is fixed the following edits would be made:
```python
channel = 3  # Router channel or None to scan
credentials = None
```
If the channel number is unknown or may vary, use
```python
channel = None
credentials = ('ssid', 'password')
```
The following demos will be installed on the node:
 1. `synctx.py` General demo of publication and subscription.
 2. `pubonly.py` Micropower publish-only demo. Assumes a FeatherS3 board.
 3. `subonly.py` Micropower subscribe-only demo.

## 3.5 Synchronous Node Testing

With the gateway running issue
```python
import nodes.synctx
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
## 3.6 Asynchronous node installation and setup

On the node device, connect to WiFi and install with
```python
import mip
mip.install("github:peterhinch/micropython-mqtt/mqtt_as/esp32_gateway/anodes")
```
Node configuration is done by editing the file `lib/anodes/link_setup.py`. This
is as per synchronous mode, but adds one variable:
 * `poll_interval = 1000`

The asynchronous link polls the gateway periodically, prompting it to send any
pending messages. This defines the interval (in ms) and determines the latency
of incoming messages.

The following demo will be installed on the node:
 1. `asynctx.py` General demo of publication and subscription.

## 3.7 Asynchronous Node Testing

With the gateway running issue
```python
import anodes.asynctx
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
# 5. The Link class

There are two versions of this supporting synchronous and asynchronous code. It
is instantiated when `link.py` or `alink.py` is imported.

## 5.1 Synchronous version

Constructor args. These are normally defined in `link_setup.py` to enable the
setup of mutiple nodes with common values.
 1. `gateway` 12 character string representing gateway ID e.g. '2462abe6b0b5'.
 2. `channel` Channel no. if known, else `None`
 3. `credentials` `('ssid', 'password')` if `channel == None` else `None`
 4. `debug=True`

Public methods:
 1. `publish(topic:str, msg:str, retain:bool=False, qos:int=0)`
 2. `subscribe(topic:str, qos:int)`
 3. `get(callback)` Receieve any pending messages. The callback will be run for
 each message. It takes args `topic:str, message:str, retained:bool`. The `get`
 method returns `True` on success, `False` on communications failure.
 4. `ping()` Check the gateway status. Returns `b"UP"` on success, `b"DOWN"` on
 broker failure or `b"FAIL"` on ESPNow comms failure.
 5. `close()` This should be run prior to `deepsleep`.
 6. `breakout(Pin)` This is a convenience function for micropower applications.
 It can be hard to get back to a REPL when `main.py` immediately restarts an
 application. Initialising `breakout` with a `Pin` instance defined with 
 `Pin.PULL_UP` allows the REPL to be regained: the node should be reset or
 power cycled with a link between the pin and gnd.
 7. `get_channel()` Query the gateway's current channel. Returns an `int` or
 `None` on fail.
 8. `reconnect()` Force a reconnection. Returns the channel number. See note
 below.
 
## 5.2 Asynchronous version

Public asynchronous methods: 
 1. `run()` This should be run on application start.
 2. `publish(topic:str, msg:str, retain:bool=False, qos:int=0)` This will block
 in the absence of ESPNow and broker connectivity.
 3. `subscribe(topic:str, qos:int)`
 4. `reconnect()` If there is a risk that the AP may change the channel this
 may be launched if a long outage occurs. See note below.

Public synchronous methods:
 1. `close()` This should be run prior to `deepsleep`.
 2. `breakout(Pin)` This is a convenience function for micropower applications.
 It can be hard to get back to a REPL when `main.py` immediately restarts an
 application. Initialising this with a `Pin` instance defined with 
 `Pin.PULL_UP` allows the REPL to be regained by resetting the node with a link
 between the pin and gnd.

Public `Event` instances:
 1. `broker_up` Set when gateway has connected to the broker.
 2. `broker_down` Set when gateway has lost connectivity with broker.
 3. `esp_up` Set when an ESPNow message is successfully sent to the gateway.
 4. `esp_down` Set when an ESPNow message has failed.

An appication using any of these events should clear them.

Message retrieval:  
The `gwlink` instance is an asynchronous iterator. Messages are retrieved with
`async for` as per this example:
```python
async def do_subs(lk):
    await lk.subscribe("foo_topic", 1)
    async for topic, message, retained in lk:
        print(f'Got subscription   topic: "{topic}" message: "{message}" retained {retained}')
```
#### Handling channel changes - This is under review

Continuously running applications started with `channel=None` automatically
track changes in channel, albeit with some message duplication. The method of
handling channel changes in micropower applications is under review.

## 5.3 Publication to all nodes

There is a topic `"allnodes"`: if an external device publishes to this topic,
the gateway will forward it to all nodes. The name of this topic may be changed
in the gateway configuration file.

# 6. The gateway

The following is reference information. The writer of node applications may
only need to be familiar with the gateway configuration. Subsequent paras
describe the internal operation of the gateway.

## 6.1 Gateway configuration

The file `gwconfig.py` instantiates a `defaultdict` with entries defining the
mode of operation of the gateway. These have default values so the file may not
need to be edited for initial testing. Keys and defaults are as follows:
```python
PubIn = namedtuple("PubIn", "topic qos")  # Publication to gateway/nodes from outside
PubOut = namedtuple("PubOut", "topic retain qos")  # Publication by gateway

gwcfg = defaultdict(lambda : None)
gwcfg["debug"] = True  # Print debug info. Also causes more status messages to be published.
gwcfg["qlen"] = 10  # No. of messages to queue (for each node).
# If queue overruns (e.g. because node is asleep), oldest messages will be lost.
gwcfg["lpmode"] = True  # Set True if all nodes are micropower: messages are queued
# and only forwarded to the node after it has published.
# If False the gateway will attempt to send the message on receipt, only queuing
# it on failure.
gwcfg["use_ap_if"] = True  # Enable ESP8266 nodes by using AP interface. This has
# the drawback of advertising an AP. If all nodes are ESP32 this may be set False
# enebling station mode to be used. Note that this affects the gateway ID.
gwcfg["pub_all"] = PubIn("allnodes", 1)  # Publish to all nodes with qos==1

# Optional keys
gwcfg["errors"] = PubOut("gw_errors", False, 1)  # Gateway publishes any errors.
gwcfg["status"] = PubOut("gw_status", False, 0)  # Destination for status reports.
gwcfg["statreq"] = PubIn("gw_query", 0)  # Status request (not yet implemented)
# gwcfg["ntp_host"] = "192.168.0.10"  # Override internet timeserver with local
gwcfg["ntp_offset"] = 1  # Local time = utc + offset
```
`PubIn` objects refer to topics to which the gateway (rather than a node) will
respond. `PubOut` topics are those to which the gateway may publish. If an
error occurs the gateway will publish it to the topic with key `"errors"`. If
"debug" is `True` the gateway will also print it.

Gateway publications may be prevented by omitting the relevant `PubOut` key.

Gateway error and status reports have a timestamp. The module will attempt to
set the ESP32 RTC from an NTP timeserver. If the NTP daemon is run on a local
host the host's IP may be specified. Alternatively time setting may be disabled
by setting `gwcfg["ntp_host"] = False`.

## 6.2 General operation

The gateway has a bound `mqtt_as` client instance (`.client`) and a dictionary
of nodes (`.queues`). The dict keys are gateway MAC addresses. Each node has
a queue for subscription messages from the client. In general messages cannot
be delivered immediately because the node my be asleep. When a node first sends
a message to the gateway a new `queues` key  is created and a queue assigned.

Messages from node to gateway are JSON-encoded lists whose length defines the
type of message. A single element list is a command, two elements denotes a
subscription and four a publication. Other lengths are ignored and an error
message published to the gateway error topic.

In the event of a broker outage, the client's publish method will block. The
gateway snds an `"ACK"` message to the node when publication is complete. This
enables the link to provide feedback to the application preventing message
loss.

If the link requests messages or queries status (via `.ping`), the gateway
responds with `"UP"` or `"DOWN"`.

## 6.3 Publications from a node

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

## 6.4 Publications to a node

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

### 6.4.2 Node setup

All nodes are set up to receive ESPNow messages via `link_setup.py`. When a
device publishes to a topic to which a node is subscribed, the gateway forwards
an ESPNow message to the node. All nodes are subscribed to the default topic.

A normal message is a JSON-encoded 3-list comprising:
 1. `topic:str`
 2. `message:str` This may itself be JSON-encoded for complex objects.
 3. `retained:bool`
`"OUT"` and `"ACK"` messages are 2-lists lacking the `retained` element.

## 6.5 Broker/WiFi outages

A node tests status by sending a `ping` message or attempting to retrieve
messages from the gateway, which responds by sending a special `"UP"` or
`"DOWN"` message to the node depending on the state of the `mqtt_as` client.
If publication is attempted during an outage the gateway responds with `"NAK"`.
The gateway will continue trying until the outage ends, when it sends `"ACK"`.

In the event of a `"NAK"` the behaviour of the link depends on whether the
synchronous or asynchronous version is running. The asynchronous `publish`
pauses until publication is complete. The synchronous version returns `False`.
The synchronous appication can keep trying to send the next message until a
`True` value occurs.

The gateway will publish status messages indicating connection state.

## 6.6 Publication to all nodes

This is done by publishing to the default topic as defined in `gwconfig.py`.
The message will be forwarded to all nodes which have communicated with the
gateway. With the default topic "allnodes":
```bash
$ mosquitto_pub -h 192.168.0.10 -t allnodes -m "hello" -q 1
```
## 6.7 Subscriptions

When a node subscribes to a topic, the gateway responds as follows. If another
node has already subscribed to this topic, the node will be added to the set of
subscribed nodes. If no other node has subscribed to this topic, the gateway
will cause the `mqtt_as` client to subscribe to the broker and will create a
record identifying the topic and the node. This ensures that future messages
are routed to that node.

## 6.8 Message integrity

Radio communications suffer from three potential issues:
 1. Corrupted messages.
 2. Duplicate messages.
 3. Missing messages.

In ESPNow Corrupted messages never seem to occur. The TCP/IP protocol ensures
they are not a problem for `mqtt_as`.

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

# 7. Node application design

## 7.1 Micropower Nodes

In general a node is designed to start, publish, optionally handle subscription
messages, deepsleep for a period, and quit. The `main.py` script restarts it;
consequently no state is retained between runs. To minimise power consumption
code should run as quickly as possible: if possible looping constructs should
be avoided. Code is typically synchronous: `uasyncio` has no support for sleep.

Messages received by the gateway and targeted on a node are queued. They are
forwarded when the node wakes up and issues `gwlink.get()`. Any messages sent
since the last wakeup will rapidly be received in the order in which they were
created. If more messages were sent than can fit in the gateway's queue, the
oldest messages will be lost.

When debugging an application it is often best to start out with `time.sleep()`
calls as this keeps the USB interface active. When the basic design is proven,
`sleep` may be replaced with `deepsleep`. Applications which deepsleep may be
debugged using a UART and an FTDI adapter.

An example of a micropower publish-only application is `pubonly.py` and is
listed in [section 2.1](./GATEWAY.md#21-micropower-publish-only-applications).
A subscribe-only application is `subonly.py`, listed below:
```python
from machine import deepsleep, Pin
from time import sleep_ms
from .link import Link
from .link_setup import gateway, channel, credentials  # Common args
gwlink = Link(gateway, channel, credentials)

# In micropower mode need a means of getting back to the REPL
# Check the pin number for your harwdware!
#link.breakout(Pin(15, Pin.IN, Pin.PULL_UP))  # Pull down for REPL.

def echo(topic, message, retained):
    gwlink.publish("shed", message)


gwlink.subscribe("foo_topic", 1)
#while True:
    #if not gwlink.get(echo):
       #print("Comms fail")
    #sleep_ms(3000)
gwlink.get(echo)  # Get any pending messages
gwlink.close()
deepsleep(3_000)
# Now effectively does a hard reset: main.py restarts the application.
```
This echos any received message to the `"shed"` topic. Messages may be sent
with
```bash
mosquitto_pub -h 192.168.0.10 -t allnodes -m "test message" -q 1
```

## 6.2 Continuous running - synchronous

If power consumption is not a concern a node may be kept running continuously.
If the AP is able to change the channel, communications will fail briefly
before recovering. There is a high probability of duplicate publications from
nodes: this seems to occur because ESPNow reports failure when the message has
been successfully sent. The `False` value from `link.publish` causes the
application to repeat the publication.

Connectivity outages can occur, for example by a node moving out of range.
These may be detected by checking the return value of `link.publish()` or by
periodically issuing `link.ping()`.

## 6.3 Continuous running - asynchronous

This is addressed by, in `link.py`, setting `channel = None`. This prompts
the gateway to briefly connect to WiFi which sets the channel. The `link`
instance has a `reconnect` method which provides a means of forcing this if the
application determines that communications have stopped for a period.

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

# 2. Files

## 2.1 Gateway

This is normally installed with `mip`. Files are listed for reference.
 1. `mqtt_as.py` MQTT client module.
 2. `mqtt_local.py` Customise to define WiFi credentials and broker IP address.
 3. `gateway.py` ESPNow gateway.
 4. `gwconfig.py` Configuration file for gateway.
 5. `primitives` directory containing `__init__.py` and `ringbuf_queue.py`.

## 2.2 Nodes

Required files are `link.py` and `link_setup.py` which should be copied from
the `nodes` directory to the device root. Note that `link_setup.py` requires
customisation before copying to identify the gateway and either WiFi channel
or WiFi credentials. See [section 4.3](./GATEWAY.md#43-gateway-setup).

The following demos are optional. The first two assume a UM FeatherS3 host:
 1. `pubonly.py` Demo of a fixed channel micropower publish-only application.
 2. `subonly.py` As above but subscribe-only.
 3. `synctx` Example of an application which runs continuously, publishing,
 handling incoming messages and doing WiFi/broker outage detection. Runs on
 any ESP32 or ESP8266.

## 5.3 General

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
