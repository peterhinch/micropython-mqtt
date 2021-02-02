# MQTT for MicroPython targets lacking WiFi connectivity

This project brings the MQTT protocol via WiFi to generic host devices running
MicroPython but lacking a WiFi interface. A cheap ESP8266 board running
firmware from this repository supplies WiFi connectivity.

It is designed to be resilient coping with WiFi or broker outages and ESP8266
failures in as near a transparent fashion as possible.

Connection between the host and the ESP8266 is via five GPIO lines.The means of
communication, and justification for it, is documented
[here](https://github.com/peterhinch/micropython-async/tree/master/syncom_as).
It is designed to be hardware independent requiring three output lines and two
inputs. It uses no hardware-specific features like timers, interrupts, special
code emitters or machine code. Nor does it make assumptions about processor
speed. It should be compatible with any hardware running MicroPython and having
five free GPIO lines.

The driver is event driven using uasyncio for asynchronous programming.
Applications can run unaffected by delays experienced on the ESP8266.

This document assumes familiarity with the umqtt and uasyncio libraries.
Unofficial guides may be found via these links:  
[umqtt FAQ](https://forum.micropython.org/viewtopic.php?f=16&t=2239&p=12694).  
[uasyncio tutorial](https://github.com/peterhinch/micropython-async/blob/master/TUTORIAL.md).

The ESP8266 operates in station mode. The host interface supports the MQTT
functionality provided in the official umqtt library. It aims to keep the link
to the broker open continuously, enabling applications which seldom or never
publish to receive messages. The host implements a watchdog to reboot the
ESP8266 in the event of fatal errors or crashes.

###### [Main README](../README.md)

# Project status (not maintained)

This project is no longer maintained and has been archived prior to development
of a replacement. The Pyboard cient requires `uasyncio` V2 with firmware V1.12.
This is obsolete. A new version will be released to use `uasyncio` V3 and with
a view to improving the API and easing portability.

V0.22 Jan 2018/April 2020

Now uses the `resilient` MQTT library. The ESP8266 is now rebooted only in the
event of ESP8266 failure such as a fatal input buffer overflow. The `resilient`
library has some significant bugfixes.

Allows custom args to `subscribe` and `wifi_handler` callbacks.

**API Changes**

The Pyboard code now uses the new task cancellation functionality in`uasyncio`.
User programs will need to be adapted to use the `@asyn.cancellable` decorator:
see `pb_simple.py`.

**Test status**

Testing was performed using a Pyboard V1.0 as the host. The following boards
have run as ESP8266 targets: Adafruit Feather Huzzah, Adafruit Huzzah and WeMos
D1 Mini.

Testing was performed using a local broker and a public one.

I have had no success with SSL/TLS. This may be down to inexperience on my part
so if anyone can test this I would welcome a report. Please raise an issue -
including to report a positive outcome :).

# Contents

 1. [Wiring](./NO_NET.md#1-wiring) Connections between host and ESP8266.  
 2. [The Host](./NO_NET.md#2-the-host) Software on the host.  
  2.1 [Files](./NO_NET.md#21-files)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.1.1 [Dependencies](./NO_NET.md#211-dependencies)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.1.2 [Test programs](./NO_NET.md#212-test-programs)  
  2.2 [Quick start guide](./NO_NET.md#22-quick-start-guide)  
  2.3 [The MQTTlink class](./NO_NET.md#23-the-mqttlink-class) The host API.  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.3.1 [Constructor](./NO_NET.md#231-constructor)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.3.2 [Methods](./NO_NET.md#232-methods)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.3.3 [Class Method](./NO_NET.md#233-class-method)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.3.4 [The user_start callback](./NO_NET.md#234-the-user_start-callback)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.3.5 [Intercepting status values](./NO_NET.md#235-intercepting-status-values)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.4 [Application design](./NO_NET.md#24-application-design)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.4.1 [User coroutines](./NO_NET.md#241-user-coroutines)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;2.4.2 [WiFi Link Behaviour](./NO_NET.md#242-wifi-link-behaviour)  
 3. [The ESP8266](./NO_NET.md#3-the-esp8266) Installing and modifying the ESP8266 build.  
  3.1 [Installing the precompiled build](./NO_NET.md#31-installing-the-precompiled-build) Quickstart.  
  3.2 [Files](./NO_NET.md#32-files) For users wishing to modify the ESP8266 code.  
  3.3 [Pinout](./NO_NET.md#33-pinout)  
 4. [Mode of operation](./NO_NET.md#4-mode-of-operation) How it works under the hood.  
  4.2 [Protocol](./NO_NET.md#42-protocol)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;4.2.1 [Initialisation](./NO_NET.md#421-initialisation)  
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;4.2.2 [Running](./NO_NET.md#422-running)  
 5. [Limitations](./NO_NET.md#5-limitations)  
  5.1 [Speed](./NO_NET.md#51-speed)  
  5.2 [Reliability](./NO_NET.md#52-reliability)  
 6. [References](./NO_NET.md#6-references)  

# 1. Wiring

Connections to the ESP8266 are as follows.

In the table below Feather refers to the Adafruit Feather Huzzah reference board
or to the Huzzah with serial rather than USB connectivity. Mini refers to the
WeMos D1 Mini. Pyboard refers to any Pyboard version. Pins are for the Pyboard
test programs, but host pins may be changed at will in `net_local.py`.


| Signal  | Feather | Mini | Pyboard | Signal  |
|:-------:|:-------:|:----:|:-------:|:-------:|
| mckin   |    12   |  D6  |   Y6    | sckout  |
| mrx     |    13   |  D7  |   Y5    | stx     |
| mtx     |    14   |  D5  |   Y7    | srx     |
| mckout  |    15   |  D8  |   Y8    | sckin   |
| reset   |  reset  |  rst |   Y4    | reset   |

Host and target must share a common ground. They need not share a common power
source - the order in which they are powered up is not critical.

Note on the reset connection. The default `net_local.py` instantiates the pin
with `Pin.OPEN_DRAIN` because some boards have a capacitor to ground. On a low
to high transition a push-pull pin could cause spikes on the power supply. The
truly paranoid might replace the reset wire with a 100Ω resistor to limit
current when the pin goes low.

###### [Contents](./NO_NET.md#contents)

# 2. The Host

The MQTT API is via the `MQTTlink` class described below.

## 2.1 Files

### 2.1.1 Dependencies

The first two files originate from the
[micropython-async](https://github.com/peterhinch/micropython-async.git)
library. For convenience all files are provided here.  
`asyn.py` Synchronisation primitives.  
`syncom.py` Bitbanged communication library.
`pbmqtt.py` Python MQTT interface.  
`status_values.py` Numeric constants shared between user code, the ESP8266
firmware and `pbmqtt.py`; including status values sent to host from ESP8266.  
`net_local.py` This enables custom settings to be shared between projects. Edit
this for WiFi credentials; also for MQTT parameters and host pin numbers if
these differ from the defaults.

### 2.1.2 Test programs

`pb_simple.py` Minimal publish/subscribe test. A remote client can turn the
Pyboard green LED on and off and can display regular publications from the
host.  
`pbmqtt_test.py` Demonstrates the ramcheck facility.  
`pbrange.py` Tests WiFi range and demos operation near the limit of range using
the Pyboard LED's for feedback.
`pb_status.py` Demonstrates the interception of status messages.

Bash scripts to periodically publish to the above test programs. Adapt to your
broker address.  
`pubtest` For `pb_simple.py` and `pbmqtt_test.py`.
`pubtest_range` For `pbrange.py`.

###### [Contents](./NO_NET.md#contents)

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
the ESP8266 [section 3.1](./NO_NET.md#31-installing-the-precompiled-build).
Copy `pb_simple.py` to the Pyboard and run it. Assuming the broker is on
192.168.0.9, on a PC run:

mosquitto_sub -h 192.168.0.9 -t result

The test program publishes an incrementing count every 10 seconds under the
"result" topic. It subscribes to a topic "green" and responds to messages "on"
or "off" to control the state of the Pyboard green LED. To test this run

mosquitto_pub -h 192.168.0.9 -t green -m on  
mosquitto_pub -h 192.168.0.9 -t green -m off

###### [Contents](./NO_NET.md#contents)

## 2.3 The MQTTlink class

This provides the host API. MQTT topics and messages are strings restricted to
7-bit ASCII characters with `ord()` values in range 1..126 inclusive.

### 2.3.1 Constructor

This takes a single mandatory argument which is a dictionary of args. Default
values are defined in `pbmqtt.py`. User overrides may be provided in
`net_local.py` or in the application. Dictionary entries are as follows
(defaults in parens):

**Hardware related:**  
`reset` A `Signal` instance associated with the reset output pin. (Y4)  
`stx` Initialised output pin. (Y5)  
`sckout` Initialised output pin with value 0. (Y6)  
`srx` Initialised input pin. (Y7)  
`sckin` Initialised input pin. (Y8)  
`timeout` Duration of ESP8266 watchdog (secs). If the ESP8266 crashes, after
this period the ESP8266 will be hard-reset. (10 secs)  
`fast` Run ESP8266 at 160MHz (recommended) (`True`)

**Callback:**  
`user_start` A callback to run when communication link is up. Mandatory.  
`args` Optional args for above. (`()`)  
The `user_start` callback runs when the link between the boards has
initialised. This is where subscriptions are registered and publishing coros
are launched. Its use is covered in detail
[below](./NO_NET.md#234-the-user_start-callback).

**WiFi parameters:**  
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

**Optional RTC synchronisation:**  
`rtc_resync` (secs). (-1)  
0 == disable.  
-1 == Synchronise once only at startup.  
If interval > 0 the ESP8266 will periodically retrieve the time from an NTP
server and send the result to the host, which will adjust its RTC. The local
time offset specified below will be applied.  
`local_time_offset` If the host's RTC is to be synchronised to an NTP
server, this allows an offset to be added. Unit is hours. (0)

**Broker/network response**  
`response_time` Max expected time in secs for the broker to respond to a
qos == 1 publication. If this is exceeded the message is republished with the
dup flag set.

**Verbosity:**  
`verbose` Pyboard prints diagnostic messages. (`False`)  
`debug` ESP8266 prints diagnostic messages. (`False`)  

###### [Contents](./NO_NET.md#contents)

### 2.3.2 Methods

 1. `publish` Args: topic (str), message (str), retain (bool), qos (0/1). Puts
 publication on a queue and returns immediately. Defaults: retain `False`,
 qos 0. `publish` can be called at any time, even if an ESP8266 reboot is in
 progress.
 2. `subscribe` Mandatory args: topic (str), qos (0/1), callback. Further
 positional args may be supplied.  
 Subscribes to the topic. The callback will run when a publication to the topic
 is received. The callback args are the topic, message plus any optional args
 supplied. Subscriptions should be performed in the `user_start`  callback to
 re-subscribe after an ESP8266 reboot. Multiple subscriptions may have separate
 callbacks.
 3. `wifi` No args. Returns `True` if WiFi and broker are up. See note below.
 4. `pubq_len` No args. Returns the length of the publication queue.
 5. `rtc_syn` No args. Returns `True` if the RTC has been synchronised to
 an NTP time server.
 6. `wifi_handler` Mandatory arg: a callback.  Further positional args may be
 supplied.  
 The callback will run each time the WiFi status changes. Callback arg is a
 `bool` followed by any user supplied args. The `bool` indicates if WiFi is up
 and the  broker is accessible. It is first called with `True` after the
 `user_start` callback completes. See note below.
 7. `status_handler` Arg: a coroutine. Overrides the default status handler.
 The coro takes two args, the `MQTTlink` instance and the status value.

Detection of outages can be slow depending on application code. The client
pings the broker, but infrequently. Detection will occur if a publication
fails provoking automatic reconnection attempts. The `ping_interval` config
value may be used to speed detection.

Methods intended for debug/test:

 1. `running` No args. Returns `True` if WiFi and broker are up and system
 is running normally.
 2. `command` Takes an arbitrary number of positional args, formats them and
 sends them to the ESP8266. Currently the only supported command is `MEM` with
 no args. This causes the ESP8266 to return its memory usage, which the host
 driver will print. This was to check for memory leaks. None have been
 observed. See `pbmqtt_test.py`.

### 2.3.3 Class Method

`will` Args topic (str), msg (str), retain, qos. Set the last will. Must be
called before instantiating the `MQTTlink`. Defaults: retain `False`, qos
0.

###### [Contents](./NO_NET.md#contents)

### 2.3.4 The user_start callback

This callback runs when broker connectivity is first established. In the event
of an ESP8266 crash, the Pyboard will reset it; the callback will subsequently
run again.

Its purpose is to register subscriptions and to launch coros which use the API.
MQTT message processing begins on the callback's return so it should run to
completion quickly.

Coroutines launched by it which communicate with the ESP8266 should have
provision to be cancelled if connectivity with the ESP8266 is lost. This can
occur if the ESP8266 crashes. The technique for doing this relies on the
cancellation API in `asyn.py` and is shown here (taken from `pb_simple.py`).

```python
@asyn.cancellable
async def publish(_, mqtt_link, tim):
    count = 1
    while True:
        mqtt_link.publish('result', str(count), 0, qos)
        count += 1
        await asyn.sleep(tim)  # Use asyn.sleep for fast cancellation response
```

Note the use of `asyn.sleep()` for delays of more than around 1s. This speeds
the response to task cancellation, which would otherwise be pending until an
`asyncio.sleep()` had elapsed.

See `pb_simple.py` and the
[synchronisation primitives docs](https://github.com/peterhinch/micropython-async/blob/master/PRIMITIVES.md).

###### [Contents](./NO_NET.md#contents)

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

###### [Contents](./NO_NET.md#contents)

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

###### [Contents](./NO_NET.md#contents)

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

# 3.1 Installing the precompiled build

You will need the esptool utility which runs on a PC. It may be found
[here](https://github.com/espressif/esptool). Under Linux after installation
you will need to assign executable status. On my system:  

`sudo chmod a+x /usr/local/bin/esptool.py`

Erase the flash with  
`esptool.py --port /dev/ttyUSB0 --baud 115200 erase_flash`  
Then, from the project directory, issue  
`esptool.py --port /dev/ttyUSB0 --baud 115200 write_flash --verify --flash_size=detect -fm qio 0 firmware-combined.bin`  
These args for the reference board may need amending for other hardware.

# 3.2 Files

In the precompiled build all modules are implemented as frozen bytecode. The
precompiled build's modules directory comprises the following:

 1. The uasyncio library (including collections directory, `errno.py`,
 `logging.py`).
 2. `mqtt.py` Main module.
 3. `mqtt_as.py` Asynchronous MQTT module.
 4. `syncom.py` Bitbanged communications driver.
 5. `status_values.py` Numeric status codes.
 6. `_boot.py` Modified to create main.py in filesystem (see below).

If flash space is limited unused drivers may be removed from the project's
`modules`. The following standard files are required:

 1. `flashbdev.py`
 2. `inisetup.py`

The `mqtt` module needs to auto-start after a hard reset. This requires a
`main.py` file. If the standard `_boot.py` is used you will need to create
the file as below and copy it to the filesystem:

```python
import mqtt
```

The modified `_boot.py` in this repository removes the need for this step
enabling the firmware image to be flashed to an erased flash chip. After boot
if `main.py` does not exist it is created in the filesystem.

###### [Contents](./NO_NET.md#contents)

# 3.3 Pinout

This is defined in `net_local.py` and passed to the `Channel` constructor in
`mqtt.py`. Pin 15 is used for mckout because this has an on-board pull down
resistor. This ensures that the ESP8266 clock line is zero while the host
asserts Reset: at that time GPIO lines are high impedance. If the pin lacks a
pull down one should be supplied. A value of 10KΩ or thereabouts will suffice.

# 4. Mode of operation

This describes the basic mode of operation for anyone wishing to modify the
host or target code. The host sends commands to the ESP8266 target, which
returns reponses. The target is responsible for keeping the link to the broker
open and reconnecting after outages. It handles qos==1 messages checking for
the correct `PUBACK` and sending duplicate messages if necessary. If a
subscribed message is received it informs the host which runs the callback.

In the event of an outage the publication response message from the target will
be delayed until the outage has ended and reconnection has occurred.

# 4.1 Communication

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

###### [Contents](./NO_NET.md#contents)

# 4.2 Protocol

## 4.2.1 Initialisation

The host instantiates an `MQTTlink` object which creates a `channel` being
a `SynCom` instance. This issues the `start` method with its own `start`
method as the coro argument. This will run every time the ESP8266 starts. If it
returns it will cause an ESP8266 reset once user coros have aborted.

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

###### [Contents](./NO_NET.md#contents)

## 4.2.2 Running

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
 it.

Expected messages are:
 1. `MEM`, free, allocated Response to a 'mem' command.
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

###### [Contents](./NO_NET.md#contents)

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
retransmissions will occur. If WiFi connectivity fails then it will persist
for the duration.

Under good conditions latency can be reduced to around 250ms.

###### [Contents](./NO_NET.md#contents)

## 5.2 Reliability

The ESP8266 is prone to unexplained crashes. In trials of extended running
these occurred about once every 24 hours. The ESP8266 UART produced repeated
`LmacRxBlk:1` messages, locking the scheduler and provoking the Pyboard to
reboot it. Such a reboot normally occurs without data loss.

The system can fail to recover from a crash in the following circumstances. If
the broker sends qos==1 messages at a high enough rate, during the ESP8266
reboot the broker accumulates a backlog. When connectivity is restored the
broker floods the ESP8266 and its buffer overflows. If the broker's backlog
continues to grow this can result in an endless boot loop.

As noted above a backlog of qos==1 messages and consequent flooding can also
occur if the ESP8266 moves out of WiFi range for a long enough period.

In testing where qos==1 messages were sent at a rate of every 20s the system
was stable and recovered without data loss from the occasional ESP8266 crash.

# 6. References

[mqtt introduction](http://mosquitto.org/man/mqtt-7.html)  
[mosquitto server](http://mosquitto.org/man/mosquitto-8.html)  
[mosquitto client publish](http://mosquitto.org/man/mosquitto_pub-1.html)  
[mosquitto client subscribe](http://mosquitto.org/man/mosquitto_sub-1.html)  
[MQTT spec](http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html#_Toc398718048)  
[python client for PC's](https://www.eclipse.org/paho/clients/python/)  
[Unofficial MQTT FAQ](https://forum.micropython.org/viewtopic.php?f=16&t=2239)

###### [Contents](./NO_NET.md#contents)
