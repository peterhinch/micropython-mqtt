# MQTT for MicroPython targets lacking WiFi connectivity

This project brings the MQTT protocol via WiFi to generic host devices running
MicroPython but lacking a WiFi interface. A cheap ESP8266 board running
firmware from this repository supplies WiFi connectivity. Tested hosts are
Pyboard 1.x and Raspberry Pi Pico. Key attributes:

 1. It is resilient coping with WiFi or broker outages and ESP8266 failures in
 a virtually transparent fashion.
 2. It is portable to other host devices by changing one simple module.
 3. Uses only `machine.Pin` instances. This avoids special functionality which
 may be absent on some ports. No RTC, timers, interrupts or special code
 emitters. Just basic Python.
 4. Five pins are used. Pin numbers may be chosen at will.
 5. Asynchronous coding is used based on `uasyncio` V3. There is no blocking on
 the host. Applications are unaffected by delays experienced on the ESP8266.
 6. The driver is event driven using callbacks.
 7. No assumptions are made about processor speed. The hardware interface
 between the ESP8266 and the host is synchronous and timing independent.
 8. The host implements a watchdog to reboot the ESP8266 in the event of fatal
 errors or crashes. This is transparent to the application.

The means of communication, and justification for it, is documented
[here](https://github.com/peterhinch/micropython-async/blob/master/v3/docs/SYNCOM.md).

It should be noted that, for a variety of reasons, it is not particularly fast.
Latency may be on the order of 250ms - see [Speed](./BRIDGE.md#51-speed). But
if using public brokers with `qos==1` latency may be significant regardless of
client.

This document assumes familiarity with the umqtt and `uasyncio` libraries.
Unofficial guides may be found via these links:  
[umqtt FAQ](https://forum.micropython.org/viewtopic.php?f=16&t=2239&p=12694).  
[uasyncio tutorial](https://github.com/peterhinch/micropython-async/blob/master/v3/docs/TUTORIAL.md).

The ESP8266 operates in station mode. The host interface supports the MQTT
functionality provided in the official umqtt library. It aims to keep the link
to the broker open continuously, enabling applications which seldom or never
publish to receive messages.

###### [Main README](../README.md)

# Project status

V0.1 Feb 2021

This should be regarded as a new module rather than as an update of the old
`pb_link`. The client module `pbmqtt.py` is a substantial rewrite with a number
of API changes. Users of `pb_link` will need to update the ESP8266 firmware.

**Test status**

Testing was performed using a Pyboard V1.0 as the host, also with a Raspberry
Pi Pico. The following boards have run as ESP8266 targets: Adafruit Feather
Huzzah, Adafruit Huzzah and WeMos D1 Mini. I have no experience of the minimal
ESP8266 boards with small amounts of flash: I would expect it to work subject
to rebuilding for the device.

Testing was performed using a local broker and a public one.

I have had no success with SSL/TLS. This is because of continuing ESP8266
firmware issues with TLS on nonblocking sockets.

# Contents

 1. [Wiring](./BRIDGE.md#1-wiring) Connections between host and ESP8266.  
 2. [The Host](./BRIDGE.md#2-the-host) Software on the host.  
  2.1 [Files](./BRIDGE.md#21-files)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.1.1 [Dependencies](./BRIDGE.md#211-dependencies)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.1.2 [Test programs](./BRIDGE.md#212-test-programs)  
  2.2 [Quick start guide](./BRIDGE.md#22-quick-start-guide)  
  2.3 [The MQTTlink class](./BRIDGE.md#23-the-mqttlink-class) The host API.  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.3.1 [Constructor](./BRIDGE.md#231-constructor)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.3.2 [Methods](./BRIDGE.md#232-methods)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.3.3 [Class Method](./BRIDGE.md#233-class-method)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.3.4 [The user_start callback](./BRIDGE.md#234-the-user_start-callback)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.3.5 [Intercepting status values](./BRIDGE.md#235-intercepting-status-values)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.4 [Application design](./BRIDGE.md#24-application-design)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.4.1 [User coroutines](./BRIDGE.md#241-user-coroutines)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.4.2 [WiFi Link Behaviour](./BRIDGE.md#242-wifi-link-behaviour)  
 3. [The ESP8266](./BRIDGE.md#3-the-esp8266) Installing and modifying the ESP8266 build.  
  3.1 [Installing the precompiled build](./BRIDGE.md#31-installing-the-precompiled-build) Quickstart.  
  3.2 [Files](./BRIDGE.md#32-files) For users wishing to modify the ESP8266 code.  
  3.3 [Pinout](./BRIDGE.md#33-pinout)  
 4. [Mode of operation](./BRIDGE.md#4-mode-of-operation) How it works under the hood.  
  4.2 [Protocol](./BRIDGE.md#42-protocol)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;4.2.1 [Initialisation](./BRIDGE.md#421-initialisation)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;4.2.2 [Running](./BRIDGE.md#422-running)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;4.2.3 [Debug methods](./BRIDGE.md#423-debug-methods)  
 5. [Limitations](./BRIDGE.md#5-limitations)  
  5.1 [Speed](./BRIDGE.md#51-speed)  
  5.2 [Reliability](./BRIDGE.md#52-reliability)  
 6. [References](./BRIDGE.md#6-references)  

# 1. Wiring

Connections to the ESP8266 are as follows.

In the table below Feather refers to the Adafruit Feather Huzzah reference board
or to the Huzzah with serial rather than USB connectivity. Mini refers to the
WeMos D1 Mini. Pyboard refers to any Pyboard version. Pins are for the Pyboard
test programs, but host pins may be changed at will in `hardware.py`.


| Signal  | Feather | Mini | Pyboard | Signal  |
|:-------:|:-------:|:----:|:-------:|:-------:|
| mckin   |    12   |  D6  |   Y6    | sckout  |
| mrx     |    13   |  D7  |   Y5    | stx     |
| mtx     |    14   |  D5  |   Y7    | srx     |
| mckout  |    15   |  D8  |   Y8    | sckin   |
| reset   |  reset  |  rst |   Y4    | reset   |
| Gnd     |   Gnd   |  G   |   GND   | 0V      |
| 5V      |   USB   |  5V  |   V+    | 5V      |

For the Pi Pico these pins are used by the test scripts. See `hw_pico.py`.

| Signal  | Feather | Mini | Pico    | Signal  |
|:-------:|:-------:|:----:|:-------:|:-------:|
| mckin   |    12   |  D6  |   18    | sckout  |
| mrx     |    13   |  D7  |   17    | stx     |
| mtx     |    14   |  D5  |   19    | srx     |
| mckout  |    15   |  D8  |   20    | sckin   |
| reset   |  reset  |  rst |   16    | reset   |
| Gnd     |   Gnd   |  G   |   GND   | 0V      |
| 5V      |   USB   |  5V  |   VBUS  | 5V      |

Host and target must share a common ground. They need not share a common power
source - the order in which they are powered up is not critical. The 5V link
enables a USB connection on the host to power the ESP8266. If the ESP8266 is
powered independently the 5V link should be omitted.

Note on the reset connection. The `hardware.py` and `hw_pico.py` files
instantiate the pin with `Pin.OPEN_DRAIN` because some boards have a capacitor
to ground. On a low to high transition a p-channel device could cause spikes on
the power supply. The truly paranoid might replace the reset wire with a 100Ω
resistor to limit current when the pin goes low.

###### [Contents](./BRIDGE.md#contents)

# 2. The Host

The MQTT API is via the `MQTTlink` class described below.

## 2.1 Files

### 2.1.1 Dependencies

These are all supplied in the `host` directory.  
`syncom.py` Bitbanged communication library.  
`pbmqtt.py` Python MQTT interface.  
`status_values.py` Numeric constants shared between user code, the ESP8266
firmware and `pbmqtt.py`; including status values sent to host from ESP8266.  
`net_local.py` Stores WiFi credentials: edit to suit.  
`hardware.py` Stores pin details. Configured for Pyboard. Edit for other hosts
or for different pin selections.

### 2.1.2 Test programs

These are located in `pyboard` and `generic` directories. The `pyboard` demos
are Pyboard-specific and use the Pyboard 1.x LED's. Those in `generic` are
similar in purpose but use serial output on the assumption that the hardware
may have no LED's available.

#### Pyboard demos

`hardware.py` Pyboard hardware configuration.  
`pb_simple.py` Minimal publish/subscribe test. A remote client can turn the
Pyboard green LED on and off and can display regular publications from the
host.  
`pbrange.py` Tests WiFi range and demos operation near the limit of range using
the Pyboard LED's for feedback.  
`pb_status.py` Demonstrates the interception of status messages.  

#### Generic demos

Tested on the Pi Pico but should be portable simply by changing `hw_pico.py`.
`hw_pico.py` Hardware config for Pi Pico  
`pico_simple.py`  
`pico_range.py`  

Bash scripts to periodically publish to the above test programs may be found in
the root directory. Adapt to your broker address.  
`pubtest` For "simple" demos.
`pubtest_range` For "range" demos.

###### [Contents](./BRIDGE.md#contents)

## 2.2 Quick start guide

Ensure you have a working MQTT broker on a known IP address, and that you have
PC client software. This document assumes `mosquitto_pub` and `mosquitto_sub`
as clients. For test purposes it's best to start with the broker on the local
network - `mosquitto` is recommended as broker.  The public brokers referenced
[here](https://github.com/mqtt/mqtt.github.io/wiki/public_brokers) may also be
used. Clients may be run on any connected PC.

Modify `net_local.py` to match your MQTT broker address, WiFi SSID and
password.

Copy the above dependencies to the Pyboard. Install the supplied firmware to
the ESP8266 [section 3.1](./BRIDGE.md#31-installing-the-precompiled-build).
Copy `pb_simple.py` to the Pyboard and run it. Assuming the broker is on
192.168.0.10, on a PC run:

mosquitto_sub -h 192.168.0.10 -t result

The test program publishes an incrementing count every 10 seconds under the
"result" topic. It subscribes to a topic "green" and responds to messages "on"
or "off" to control the state of the Pyboard green LED. To test this run

mosquitto_pub -h 192.168.0.10 -t green -m on  
mosquitto_pub -h 192.168.0.10 -t green -m off

###### [Contents](./BRIDGE.md#contents)

## 2.3 The MQTTlink class

This provides the host API. MQTT topics and messages are strings restricted to
7-bit ASCII characters with `ord()` values in range 1..126 inclusive.

The constructor creates a dictionary containing a number of configuration
values. These are indexed by name and are listed below. The constructor args
are designed to provide a variety of ways to specify these values. The
constructor will update the dictionary with any dictionaries passed as
positional args. It can also add individual parameters passed a keyword args.

The file `pbmqtt.py` pre-populates the dictionary with default values for most
parameters, but these may be overridden as required.

### 2.3.1 Constructor

This takes any number of positional args, being dictionaries of values. The
typical invocation below imports hardware and network details from files,
adding three values as keyword args:
```python
from pbmqtt import MQTTlink
import hardware
import net_local
# Code omitted e.g. defining a start function.
mqtt_link = MQTTlink(hardware.d, net_local.d, user_start=start, debug=True, verbose=True)
```
Dictionary entries are as follows (defaults in parens):

**Hardware related:**  
Typically stored in `hardware.py`  
`reset` A `Signal` instance associated with the reset output pin. (Y4)  
`stx` Initialised output pin. (Y5)  
`sckout` Initialised output pin with value 0. (Y6)  
`srx` Initialised input pin. (Y7)  
`sckin` Initialised input pin. (Y8)  
`timeout` Duration of ESP8266 watchdog (secs). If the ESP8266 crashes, after
this period the ESP8266 will be hard-reset. (10 secs)  
`fast` Run ESP8266 at 160MHz (recommended) (`True`)
`led` If provided this should be a `machine.Pin` object initialised as an
output. This will periodically be toggled. If no heartbeat LED is required, the
key should be unused.

**Callbacks:**  
Callbacks are specified as a 2-tuple consisting of the callback and a tuple of
arguments. The latter may be empty (`()`). In each case a "no callback" default
is provided so overriding these is optional.  
`user_start=(cb, ())` Callback runs when communication link is up. It runs when
the link between the boards is first initialised, and also after recovery from
an ESP8266 crash. Received args are the link instance followed by any user
args. Its use is covered in detail
[below](./BRIDGE.md#234-the-user_start-callback).  
`wifi_handler=(cb, ())` Callback runs whenever WiFi status changes. Receives as
two first args a `bool` being the new WiFi state followed by the link instance.
See `pb_simple.py`.  
`crash_handler=(cb, ())` Callback runs if ESP8266 crashes. Typically used to
cancel tasks started by `user_start`.
`status_handler=(coro, ())` A coroutine. Launched when the ESP8266 reports
changed status. Received args are the link instance and the numeric status
value from the ESP8266 followed by any user args. It should normally await the
`default_status_handler` coroutine in `pbmqtt.py`. See `pb_status.py`.

**WiFi parameters:**  
Typically stored in `net_local.py`  
`ssid` Mandatory. No default.  
`password` Mandatory. No default.  
`use_default_net` Use default network if possible. (`True`)  
If `True`, tries to connect to the network stored on the ESP8266. If this
fails, it will connect to the specified network.  
If `False`, ignores the saved LAN. The specified LAN becomes the new default.

**MQTT parameters:**  
`broker` IP address of broker. Mandatory. No default.  
`mqtt_user` Username ('')  
`mqtt_pw` Password ('')  
`ssl` Use SSL (`False`)  
`ssl_params` Repr of dict. (`repr({})`)  
`port` If 0 uses the default MQTT port. (0)  
`keepalive` Broker keepalive time (secs) (60)  
`ping_interval` Time between broker pings (secs) (0) (0 == use default)  
`max_repubs` Max number of qos==1 republications before reonnection is
initiated (4).  
`clean_session` Behaviour after an outage. (`True`)  
The Clean Session flag controls behaviour of qos == 1 messages from the broker
after a WiFi outage which exceeds the broker's keepalive time. (MQTT spec
section 3.1.2.4).

If set, such messages from the broker during the outage will be lost. If
cleared the broker will send them once connectivity is restored. This presents
a hazard in that the ESP8266 WiFi stack has a buffer which can overflow if
messages arrive in quick succession. This could result in an ESP8266 crash with
a consequent automatic reboot, in which case some of the backlog will be lost.

The client pings the broker up to four times in the `keepalive` period. In the
case of applications which publish rarely or never, pinging more frequently
speeds the detection of outages. The `ping_interval` parameter enables this to
be accomplished. The default value of 0 results in standard behaviour.

**Broker/network response**  
`response_time` Max expected time in secs for the broker to respond to a
qos == 1 publication. If this is exceeded the message is republished with the
dup flag set.

**Time server**

`'timeserver` Default 'pool.ntp.org'.

**Verbosity:**  
`verbose` Pyboard prints diagnostic messages. (`False`)  
`debug` ESP8266 prints diagnostic messages to its serial output. (`False`)  

###### [Contents](./BRIDGE.md#contents)

### 2.3.2 Methods

Bound coroutines. Required in most applications:
 1. `publish` Args: topic (str), message (str), retain (bool), qos (0/1).  
 Pauses until WiFi is up and a response has been received from the ESP8266.
 Defaults: `retain=False`, `qos=0`. The `publish` task can be launched at any
 time, even if an ESP8266 reboot is in progress. In the case of `qos==1` return
 will be delayed until the ESP8266 has received a `PUBACK` from the broker.
 2. `subscribe` Mandatory args: topic (str), qos (0/1), callback. Further
 positional args may be supplied.  
 Subscribes to the topic. The callback will run when a publication to the topic
 is received. The callback args are the topic, message, the `retained message`
 flag followed by any optional args supplied.  
 Subscriptions should be performed after waiting for initial `ready` status.
 Multiple subscriptions may have separate callbacks. In the event of an outage
 re-subscription is automatic.
 3. `get_time` Args `pause=120, y2k=False`. This attempts to retrieve time from
 an NTP server. Returns a time value in seconds since the epoch. If `y2k` is
 `True` the epoch is 2000-01-01 00:00:00 UTC, otherwise it is the epoch as
 defined on the host device. A host epoch ensures that `time.localtime()` will
 produce a valid result.  
 In the event of failure it will pause for `pause` seconds before again
 querying a timeserver. In the event of communication problems the task can
 therefore pause for some time until a valid time is acquired. When this occurs
 return is fast. Typical usage is to set the RTC.  
 A call to `get_time` causes the ESP8266 to issue `socket.getaddrinfo()` which
 unfortunately is currently a blocking call: the ESP8266 blocks for a period
 but the host does not. This can delay overall responsiveness for the duration.
 4. `ready` No arg. `await mqttlink.ready()` returns when the link is up.

 Synchronous methods:
 1. `wifi` No args. Returns `True` if WiFi and broker are up.  
 Detection of outages can be slow depending on application code. The client
 pings the broker, but infrequently. Detection will occur if a publication
 fails provoking automatic reconnection attempts. The `ping_interval` config
 value may be used to speed detection.

### 2.3.3 Class Method

`will` Args topic (str), msg (str), retain, qos. Set the last will. Must be
called before instantiating the `MQTTlink`. Defaults: retain `False`, qos
0.

###### [Contents](./BRIDGE.md#contents)

### 2.3.4 The user_start callback

This callback runs when broker connectivity is first established. In the event
of an ESP8266 crash, the Pyboard will reset the ESP so the callback will
subsequently run again.

Its purpose is to launch coros which use the API or which need to respond to
ESP8266 recovery.

```python
async def foo(mqtt_link, tim):
    while True:
        # Do something involving ESP8266
        await asyncio.sleep(tim)

def start(mqtt_link):
    asyncio.create_task(foo(mqtt_link, 10))

mqtt_link = MQTTlink(hardware.d, net_local.d, user_start=(start, ()))
```
Note that the specified `start` function receives the `MQTTlink` instance as
its first arg, followed by any user specified args.

See the test script `pbrange.py`.

###### [Contents](./BRIDGE.md#contents)

### 2.3.5 Intercepting status values

A typical reason for interception is to handle fatal errors on initial startup,
for example where the WiFi network or broker is unavailable. Options might be
to prompt for user intervention or pausing for a period before rebooting.

The ESP8266 can send numeric status values to the host. These are defined and
documented in `status_values.py`. The default handler specifies how a network
connection is established after a reset. Initially, if the ESP8266 fails to
connect to the default LAN stored in its flash memory, it attempts to connect
to the network specified in `INIT`. On ESP8266 reboots (caused by a crash) it
saves flash wear by avoiding the specified LAN; it waits 30 seconds and
reboots again.

The behaviour in response to status messages may be modified by replacing the
default handler with a user supplied coroutine as described in 2.3.2 above;
the test program `pb_status.py` illustrates this.

The driver waits for the handler to terminate, then responds in a way dependent
on the status value. If it was a fatal error the ESP8266 will be rebooted. For
informational values execution will continue.

The return value from the coroutine is ignored except in response to a
`SPECNET` message. If it returns 1 the driver will attempt to connect to the
specified network. If it returns 0 it will reboot the ESP8266.

###### [Contents](./BRIDGE.md#contents)

## 2.4 Application design

### 2.4.1 User coroutines

Where possible these should periodically yield to the scheduler with a nonzero
delay. An `asyncio.sleep(secs)` or `aysncio.sleep_ms(ms)` will reduce
competition with the bitbanging communications, minimising any impact on
throughput. Issue a zero delay (or `yield`) only when a fast response is
required.

### 2.4.2 WiFi Link Behaviour

The implicit characteristics of radio links mean that WiFi is subject to
outages of arbitrary duration: RF interference may occur, or the unit may move
out of range of the access point.

This driver aims to handle outages as transparently as possible. If an outage
occurs the ESP8266 signals the driver that this has occurred, signalling again
when connectivity is restored. These events may be trapped by intercepting the
status messages (see `pbrange.py`) or - simpler - by using the `wifi_handler`
(`pb_simple.py`).

During an outage publications will be queued. An ongoing qos==1 publication
will be delayed until connectivity is restored. Messages from the broker with
qos==1 will be queued by the broker and will be received when connectivity
recovers. This will end when the broker's keepalive time expires, when any last
will is published. Whether the qos==1 messages are retransmitted then depends
on the state of the `Clean Session` flag in `net_local.py`.

Note that the ESP8266 vendor network stack has a buffer which can overrun if
messages are sent in rapid succession. If you encounter lost messages and see
`LmacRxBlk:1` on the ESP8266 UART this is the cause.

###### [Contents](./BRIDGE.md#contents)

# 3. The ESP8266

To use the precompiled build, follow the instructions in 3.1 below. The
remainder of the ESP8266 documentation is for those wishing to modify the
ESP8266 code. 

The firmware toggles pin 0 to indicate that the code is running. Pin 2 is
driven low when broker connectivity is present. On the reference board this
results in the blue LED indicating connectivity status and the red LED flashing
while running.

Since the Pyboard and the ESP8266 communicate via GPIO pins the UART/USB
interface is available for checking status messages and debugging.

## 3.1 Installing the precompiled build

You will need the esptool utility which runs on a PC. It may be found
[here](https://github.com/espressif/esptool). Under Linux after installation
you will need to assign executable status. On my system:  

`sudo chmod a+x /usr/local/bin/esptool.py`

Erase the flash (this is essential) with  
`esptool.py --port /dev/ttyUSB0 --baud 115200 erase_flash`  
Then, from the bridge directory, issue  
`esptool.py --port /dev/ttyUSB0 --baud 115200 write_flash --verify --flash_size=detect -fm qio 0 firmware-combined.bin`  
These args for the reference board may need amending for other hardware.

## 3.2 Files

If you want to build this yourself the first step is to acquire the ESP8266
toolchain and verify that you can create a working standard ESP8266 build.

The following steps are required. Create a directory on your PC for Python
files for freezing. Populate it with the following files:

 1. `mqtt.py` Main module (esp8266 directory).
 2. `mqtt_as.py` Asynchronous MQTT module (mqtt_as directory).
 3. `syncom.py` Bitbanged communications driver (host directory).
 4. `status_values.py` Numeric status codes (host directory).
 5. `_boot.py` Modified to create main.py in filesystem (esp8266 directory).
From micropython source tree (ports/esp8266/modules):  
 6. `flashbdev.py` 
 7. `inisetup.py`

The `mqtt` module needs to auto-start after a hard reset. This requires a
`main.py` file with the following contents:

```python
import mqtt
```

The modified `_boot.py` in this repository creates this automatically, enabling
the firmware image to be flashed to an erased flash chip. After boot, if
`main.py` does not exist it is created in the filesystem.

To build the code it is necessary to create a manifest file on your PC. In my
case it is called `mqtt_manifest.py`. It should have the following contents
(adjusting the path to your frozen directory).
```python
# Manifest for ESP8266 firmware for MQTT bridge
include("$(MPY_DIR)/extmod/uasyncio/manifest.py")
freeze('/path/to/frozen')
```
I use the following script to build the firmware:
```bash
#! /bin/bash
# Build for mqtt ESP8266

PROJECT_DIR='/mnt/qnap2/data/Projects/MicroPython/micropython-mqtt/bridge/'
MANIFESTS='/mnt/qnap2/Scripts/manifests'
MANIFEST=$MANIFESTS/mqtt_manifest.py

cd /mnt/qnap2/data/Projects/MicroPython/micropython/ports/esp8266
make clean
esptool.py  --port /dev/ttyUSB0 erase_flash

if make -j 8 FROZEN_MANIFEST=$MANIFEST
then
    cp build-GENERIC/firmware-combined.bin $PROJECT_DIR
    sleep 1
    esptool.py --port /dev/ttyUSB0 --baud 115200 write_flash --verify --flash_size=detect -fm dio 0 build-GENERIC/firmware-combined.bin
    cd -
    sleep 1
#    rshell -p /dev/ttyUSB0 --editor nano --buffer-size=30
else
    echo Build failure
fi
cd -
```

###### [Contents](./BRIDGE.md#contents)

## 3.3 Pinout

ESP8266 pinout is defined by the `Channel` constructor in `mqtt.py`. Pin 15 is
used for `mckout` because this has an on-board pull down resistor. This ensures
that the ESP8266 clock line is zero while the host asserts Reset: at that time
GPIO lines are high impedance. If the pin lacks a pull down one should be
supplied. A value of 10KΩ or thereabouts will suffice.

# 4. Mode of operation

This describes the basic mode of operation for anyone wishing to modify the
host or target code. The host sends commands to the ESP8266 target, which
returns reponses. The target is responsible for keeping the link to the broker
open and reconnecting after outages. It handles qos==1 messages checking for
the correct `PUBACK` and sending duplicate messages if necessary. If a
subscribed message is received it informs the host which runs the callback.

In the event of an outage the publication response message from the target will
be delayed until the outage has ended and reconnection has occurred.

## 4.1 Communication

The host and target communicate by a symmetrical bidirectional serial protocol.
At the hardware level it is full-duplex, synchronous and independent of
processor speed. At the software level it is asynchronous. In this application
the unit of communication is a string. When a `SynCom` is instantiated it
does nothing until its asynchronous `start` method is launched. This takes a
coroutine as an argument. It waits for the other end of the link to start,
synchronises the interface and launches the coro.

In the case of the host this runs forever except on error when it terminates.
The host has a means of issuing a hardware reset to the target, triggered by
the coro terminating. The `SynCom` instance resets the target, waits for synch,
and re-launches the coro (`SynCom` start method).

The ESP8266 has no means of resetting the host, so there is no reason for its
coro (`main_task`) to end.

The interface also provides a means for the host to detect if the ESP8266 has
crashed or locked up. To process incoming messages it issues

```python
chan_state = channel.any()
```

A result of `None` means that the channel has timed out which is a result of
ESP8266 failure. In this instance the coro quits causing the ESP8266 to be
reset.

###### [Contents](./BRIDGE.md#contents)

## 4.2 Protocol

These details are provided for those wishing to modify the ESP8266 code.

### 4.2.1 Initialisation

The host instantiates an `MQTTlink` object which creates a `channel` being
a `SynCom` instance. This issues the `start` method with its own `start`
method as the coro argument. This will run every time the ESP8266 starts. If it
returns it will cause an ESP8266 reset after running any user crash handler.

The host can send commands to the ESP8266 which replies with a status response.
The ESP8266 can also send unsolicited status messages. When a command is sent
the host waits for a response as described above, handling a `None` response.
The string is parsed into a command - typically `STATUS` - and an action, a
list of string arguments. In the case of `STATUS` messages the first of these
args is the status value.

Status messages are first passed to the `do_status` method which performs
some basic housekeeping and provides optional 'verbose' print messages. It
returns the (possibly amended) status value as an integer. It then waits on the
asynchronous method `s_han` which by default is `default_status_handler`. This
can be overridden by the user.

Each time the `start` method runs it behaves as follows. If the user has set
up a will, it sends a `will` command to the ESP8266 and waits for a status
response.

Assuming success it then sends an `init` command with the `INIT` parameters
which causes the ESP8266 to connect to the WiFi network and then to the broker.
The initialisation phase ends when the ESP8266 sends a `RUNNING` status to
the host, when `_running` is set (by `do_status`). In the meantime the
ESP8266 will send other status messages:

 1. `DEFNET` It is about to try the default network in its flash ROM.
 2. `SPECNET` It has failed to connect to this LAN and wants to connect to
 the one specified in `INIT`. Unless the status handler has been overridden
 `default_status_handler` ensures this is done on the first boot only.
 3. `BROKER_CHECK` It is about to connect to the broker.
 4. `BROKER_OK` Broker connection established.

Once running it launches the user supplied coroutine. It also launches a coro
to handle publications: the `_publish` asynchronous method. It triggers the
wifi callback to indicate readiness; the initialisation phase is now complete
and it enters the running phase.

Subscriptions are handled as follows. The user may issue
```python
asyncio.create_task(mqtt_link.subscribe('green', qos, cbgreen))
```
at any time. If the link is not yet initialised this task will pause until it
is, and then send a subscription message to the ESP8266. The task will also
store the details of the subscription in a dict. If the ESP8266 has to be
re-booted, the dict will be used to re-create the subscriptions.

###### [Contents](./BRIDGE.md#contents)

### 4.2.2 Running

This continuously running loop exits only on error when the ESP8266 is to be
rebooted. It waits on incoming messages from the ESP8266 (terminating on
`None` which indicates a watchdog timeout).

The ESP8266 can send various messages, some such as `SUBSCRIPTION`
asynchronously in response to a broker message and others such as a `PUBOK`
status in response to having processed a qos == 1 'publish' message from the
host. Unsolicited messages are:

 1. `SUBSCRIPTION` A message published to a user subscription was received.
 2. `TIME`, value The ESP8266 has contacted a timeserver and has received this
 time value.
 3. `STATUS`, `WIFI_UP`
 4. `STATUS`, `WIFI_DOWN`
 5. `STATUS`, `UNKNOWN` This should never occur. ESP8266 has received an unknown
 command from the host or is failing to respond correctly. The driver reboots
 the ESP8266.

Expected messages are:
 1. `MEM`, free, allocated. Response to a 'mem' command.
 2. `STATUS`, `PUBOK` Response to a qos == 1 publication.

User publications are placed on a queue which is serviced by the host's
`_publish` coroutine. When it issues a publication it informs the ESP8266 and
sets a flag. This locks out further publications until a `PUBOK` is received
from the ESP8266. In the case of qos==1 this occurs when the broker sends a
PUBACK with the correct PID. A `PUBOK` clears the flag, re-enabling
publications which resume if any are queued. See `pub_free()`.

In the case of a qos==0 publication the ESP8266 will respond with `PUBOK`
immediately as no response is expected from the broker.

There is a potential for overloading the ESP8266 if the publication queue fills
during an outage. The `_publish` coro pauses after completion of a publication
before sending another. It also implements a timeout where no response arrives
from the ESP8266 when the network is available; in this case the ESP8266 is
assumed to have failed and is reset.

### 4.2.3 Debug methods

The MQTTlink class has these methods intended for debug/test:  
 1. `running` Synchronous. No args. Returns `True` if ESP8266 is running
 normally.
 2. `command` Asynchronous. Takes an arbitrary number of positional args,
 formats them and sends them to the ESP8266. Currently the only supported
 command is `MEM` with no args. This causes the ESP8266 to return its memory
 usage, which the host driver will print. This was to check for memory leaks.
 None have been observed. A simpler way is to connect a terminal to the ESP8266
 which reports its RAM use periodically.

###### [Contents](./BRIDGE.md#contents)

# 5. Limitations

## 5.1 Speed

The performance of MQTT can be limited by the connection to the broker, which
can be slow if the broker is on the internet. This implementation is also
constrained by the performance of the serial interface. Under operational
conditions this was measured at 118 chars/sec (chars are 7-bit).

In applications such as data logging this is not usually an issue. If latency
matters, keep topic names and messages short and (if possible) use a broker on
the LAN.

Latency will degrade if using qos==1 on a poor WiFi link, because
retransmissions will occur. If WiFi connectivity fails then latency persists
for the duration.

Under good conditions latency can be reduced to around 250ms.

###### [Contents](./BRIDGE.md#contents)

## 5.2 Reliability

The ESP8266 is prone to unexplained crashes. In trials of extended running
these occurred about once every 24 hours. The ESP8266 UART produced repeated
`LmacRxBlk:1` messages, locking the scheduler and provoking the Pyboard to
reboot it.

ESP8266 reboots normally occur without data loss, but this is not guaranteed.
Even `qos==1` transmissions may occasionally be lost in these circumstances.

The system can fail to recover from a crash in the following circumstances. If
the broker sends qos==1 messages at a high enough rate, during the ESP8266
reboot the broker accumulates a backlog. When connectivity is restored the
broker floods the ESP8266 and its buffer overflows. If the broker's backlog
continues to grow this can result in an endless boot loop.

As noted above a backlog of qos==1 messages and consequent flooding can also
occur if the ESP8266 moves out of WiFi range for a long enough period.

In testing where qos==1 messages were sent at a rate of every 20s the system
was stable and recovered without data loss from the occasional ESP8266 crash.

In use the ESP8266 reports just over 10KB RAM used and 27KB free.

# 6. References

[mqtt introduction](http://mosquitto.org/man/mqtt-7.html)  
[mosquitto server](http://mosquitto.org/man/mosquitto-8.html)  
[mosquitto client publish](http://mosquitto.org/man/mosquitto_pub-1.html)  
[mosquitto client subscribe](http://mosquitto.org/man/mosquitto_sub-1.html)  
[MQTT spec](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718048)  
[python client for PC's](https://www.eclipse.org/paho/clients/python/)  
[Unofficial MQTT FAQ](https://forum.micropython.org/viewtopic.php?f=16&t=2239)

###### [Contents](./BRIDGE.md#contents)
