# Bringing MQTT to MicroPython targets

MQTT is an easily used networking protocol designed for IOT (internet of
things) applications. It is well suited for controlling hardware devices and
for reading sensors across a local network or the internet.

The aim of this project is to bring the protocol via WiFi to generic host
devices running MicroPython but lacking a WiFi interface. A cheap ESP8266 board
running firmware from this repository supplies WiFi connectivity. Connection
between the host and the ESP8266 is via five GPIO lines. The means of
communication, and justification for it, is documented
[here](https://github.com/peterhinch/micropython-async/tree/master/syncom_as).
It is designed to be hardware independent requiring three output lines and two
inputs. It uses no hardware-specific features like timers, interrupts or
machine code, nor does it make assumptions about processor speed. It should be
compatible with any hardware running MicroPython and having five free GPIO
lines.

The driver is event driven using uasyncio for asynchronous programming.
Applications continue to run unaffected by delays experienced on the ESP8266.

This document assumes familiarity with the umqtt and uasyncio libraries.
Unofficial guides may be found via these links:  
[umqtt FAQ](https://forum.micropython.org/viewtopic.php?f=16&t=2239&p=12694).  
[uasyncio tutorial](https://github.com/peterhinch/micropython-async/blob/master/TUTORIAL.md).

The ESP8266 operates in station mode. The host interface aims to support all
the MQTT functionality provided in the umqtt library. It tries to keep the link
to the broker open continuously, allowing applications which seldom or never
publish. The ESP8266 firmware and the host interface are designed to be
resilient under error conditions. The ESP8266 is rebooted in the event of fatal
errors or crashes.

# Project status

At the time of writing (June 2017) the code is best described as being of beta
quality. Testing has been done with a local broker. It is untested with a
broker on the WAN, also with SSL. If anyone is in a position to test these I
would welcome reports. Please raise an issue - including to report positive
outcomes :).

Testing was performed using a Pyboard V1.0 as the host. The following boards
have run as ESP8266 targets: Adafruit Feather Huzzah, Adafruit Huzzah and WeMos
D1 Mini.

Originally written when the ESP8266 firmware was error-prone it has substantial
provision for error recovery. Much of the code deals with events like blocked
sockets, ESP8266 crashes and WiFi and broker outages. The underlying stability
of MicroPython on the ESP8266 is now excellent, but wireless networking remains
vulnerable to error conditions such as radio frequency interference or the host
moving out of range of the access point.

# Contents

 1 [Wiring](./README.md#1-wiring)
 
 2 [The Host](./README.md#2-the-host)

  2.1 [Files](./README.md#21-files)

   2.1.1 [Dependencies](./README.md#211-dependencies)

   2.1.2 [2.1.2 Test programs](./README.md#212-test-programs)

  2.2 [Quick start guide](./README.md#22-quick-start-guide)

  2.3 [The MQTTlink class](./README.md#23-the-mqttlink-class)

   2.3.1 [Constructor](./README.md#231-constructor)

   2.3.2 [Methods](./README.md#232-methods)

   2.3.3 [Class Method](./README.md#233-class-method)

   2.3.4 [Intercepting status values](./README.md#234-intercepting-status-values)

   2.3.5 [The user_start callback](./README.md#235-the-user_start-callback)

  2.4 [Application design](./README.md#24-application-design)

   2.4.1 [User coroutines](./README.md#241-user-coroutines)

   2.4.2 [WiFi Link Behaviour](./README.md#242-wifi-link-behaviour)

 3 [The ESP8266](./README.md#3-the-esp8266)
 
  3.1 [Installing the precompiled build](./README.md#31-installing-the-precompiled-build)

  3.2 [Files](./README.md#32-files)

  3.3 [Pinout](./README.md#33-pinout)
 
 4 [Mode of operation](./README.md#4-mode-of-operation)

  4.2 [Protocol](./README.md#42-protocol)

  4.2.1 [Initialisation](./README.md#421-initialisation)

  4.2.2 [Running](./README.md#422-running)

 5 [Postscript](./README.md#5-postscript)

# 1. Wiring

Connections to the ESP8266 are as follows.

In the table below Feather refers to the Adafruit Feather Huzzah reference board
or to the Huzzah with serial rather than USB connectivity. Mini refers to the
WeMos D1 Mini. Pyboard refers to any Pyboard version. Pins are for the Pyboard
test programs, but host pins may be changed at will in the application code.


| Signal  | Feather | Mini | Pyboard | Signal  |
|:-------:|:-------:|:----:|:-------:|:-------:|
| mckin   |    12   |  D6  |   Y6    | sckout  |
| mrx     |    13   |  D7  |   Y5    | stx     |
| mtx     |    14   |  D5  |   Y7    | srx     |
| mckout  |    15   |  D8  |   Y8    | sckin   |
| reset   |  reset  |  rst |   Y4    | reset   |

Host and target must share a sigle power supply with a common ground.

###### [Contents](./README.md#contents)

# 2. The Host

The MQTT API is via the ``MQTTlink`` class described below.

## 2.1 Files

### 2.1.1 Dependencies

The following files originate from the [micropython-async](https://github.com/peterhinch/micropython-async.git) library.  
``aswitch.py`` Provides a retriggerable delay class.  
``asyn.py`` Synchronisation primitives.  
``syncom.py`` Communication library.

From this library:  
``pbmqtt.py`` Python MQTT interface.  
``status_values.py`` Numeric constants shared between user code, the ESP8266
firmware and ``pbmqtt.py``; including status values sent to host from ESP8266.  
``net_local.py`` Local network credentials and MQTT parameters. Edit this.

### 2.1.2 Test programs

``pb_simple.py`` Minimal publish/subscribe test. A remote unit can turn the
Pyboard green LED on and off and can display regular publications from the
host.  
``pb_status.py`` Demonstrates interception of status messages.  
``pbmqtt_test.py`` Tests coroutines which must shut down on ESP8266 reboot.
Also demonstrates the ramcheck facility.

###### [Contents](./README.md#contents)

## 2.2 Quick start guide

Ensure you have a working MQTT broker on a known IP address, and that you have
PC client software. This document assumes mosquitto as broker, mosquitto_pub
and mosquitto_sub as clients. For test purposes it's best to start with the
broker on the local network. Clients may be run on any connected PC.

Modify ``net_local.py`` to match your MQTT broker address, WiFi SSID and
password.

Copy the above dependencies to the Pyboard. Install the supplied firmware to
the ESP8266 (section 3.1). Copy ``pb_simple.py`` to the Pyboard and run it.
Assuming the broker is on 192.168.0.9, on a PC run:

mosquitto_sub -h 192.168.0.9 -t result

The test program publishes an incrementing count every 10 seconds under the
"result" topic. It subscribes to a topic "green" and responds to messages "on"
or "off" to control the state of the Pyboard green LED. To test this run

mosquitto_pub -h 192.168.0.9 -t green -m on  
mosquitto_pub -h 192.168.0.9 -t green -m off

###### [Contents](./README.md#contents)

## 2.3 The MQTTlink class

### 2.3.1 Constructor

This takes the following positional args:
 1. ``reset`` A ``Signal`` instance associated with the reset output pin. The
 test programs instantiate the pin with ``Pin.OPEN_DRAIN`` because some boards
 have a capacitor to ground. On a low to high transition a push-pull pin could
 cause spikes on the power supply. The truly paranoid might replace the reset
 wire with a 100Ω resistor to limit current.
 2. ``sckin`` Initialised input pin.
 3. ``sckout`` Initialised output pin with value 0.
 4. ``srx`` Initialised input pin.
 5. ``stx`` Initialised output pin with value 0.
 6. ``init`` A tuple of initialisation values. See below.
 7. ``user_start=None`` A callback to run when communication link is up.
 8. ``args=()`` Optional args for above.
 9. ``local_time_offset=0`` If the host's RTC is to be synchronised to an NTP
 server, this allows an offset to be added. Unit is hours.
 10. ``verbose=True`` Print diagnostic messages.
 11. ``timeout=10`` Duration of ESP8266 watchdog (secs). This limits how long a
 socket can block before the ESP8266 is rebooted. If the broker is on a slow
 internet connection this should be increased.

The ``user_start`` callback runs when the link between the boards has
initialised. If the ESP8266 crashes the link times out and the driver resets
the ESP8266. When the link is re-initialised ``user_start`` runs again. Typical
use is to define subscriptions. The callback can launch coroutines but these
should run to completion promptly (less than a few seconds). If such coros run
forever, precautions apply. See section 2.3.5.

``INIT``: a tuple of data to be sent to ESP8266 after a reset.  
Init elements. Entries 0-6 are strings, 7-12 are integers:

 0. 'init'
 1. SSID for WiFi.
 2. WiFi password.
 3. Broker IP address.
 4. MQTT user ('' for none).
 5. MQTT password ('' for none).
 6. SSL params (repr of a dictionary)
 7. 1/0 Use default network if possible. If 1, tries to connect to the network
 stored on the ESP8266. If this fails, it will connect to the specified
 network. If 0, ignores the saved LAN. The specified LAN becomes the new
 default.
 8. port: use 0 for default.
 9. 1/0 ssl
 10. 1/0 fast: if 1, clock ESP8266 at 160MHz
 11. RTC resync interval (secs). 0 == disable. If interval > 0 the ESP8266 will
 periodically retrieve the time from an NTP server and send the result to the
 host, which will adjust its RTC. The local  time offset specified to the
 constructor will be applied. If interval == -1 synchronisation will occur once
 only.
 12. keepalive time (secs) (0 = disable). Sets the broker keepalive time.

###### [Contents](./README.md#contents)

### 2.3.2 Methods

 1. ``publish`` Args topic (str), message (str), retain (bool), qos (0/1). Puts
 publication on a queue and returns immediately. Defaults: retain ``False``,
 qos 0. ``publish`` can be called at any time, even if an ESP8266 reboot is in
 progress.
 2. ``subscribe`` Args topic (str), callback, qos (0/1). Subscribes to the
 topic. The callback will run when a publication is received. The callback args
 are the topic and message. It should be called from the ``user_start``
 callback to re-subscribe after an ESP8266 reboot.
 3. ``pubq_len`` No args. Returns the length of the publication queue.
 4. ``rtc_syn`` No args. Returns ``True`` if the RTC has been synchronised to
 an NTP time server.
 5. ``status_handler`` Arg: a coroutine. Overrides the default status handler.
 6. ``running`` No args. Returns ``True`` if WiFi and broker are up and system
 is running normally.
 7. ``command`` Intended for test/debug. Takes an arbitrary number of
 positional args, formats them and sends them to the ESP8266. Currently the
 only supported command is 'mem' with no args. This causes the ESP8266 to
 return its memory usage, which the host driver will print. This was to check
 for memory leaks. None have been observed. See ``pbmqtt_test.py``.

### 2.3.3 Class Method

``will`` Args topic (str), msg (str), retain, qos. Set the last will. Must be
called before instantiating the ``MQTTlink``. Defaults: retain ``False``, qos
0.

###### [Contents](./README.md#contents)

### 2.3.4 Intercepting status values

The ESP8266 can send numeric status values to the host. These are defined and
documented in ``status_values.py``. The default handler specifies how a network
connection is established after a reset. Initially, if the ESP8266 fails to
connect to the default LAN stored in its flash memory, it attempts to connect
to the network specified in ``INIT``. On ESP8266 reboots it avoids flash wear
by avoiding the specified LAN; it waits 30 seconds and reboots again.

The behaviour in response to status messages may be modified by replacing the
default handler with a user supplied coroutine as described in 2.3.2 above;
the test program ``pb_status.py`` illustrates this.

The driver waits for the handler to terminate, then responds in a way dependent
on the status value. If it was a fatal error the ESP8266 will be rebooted. For
informational values execution will continue.

The return value from the coroutine is ignored except in response to a
``SPECNET`` message. If it returns 1 the driver will attempt to connect to the
specified network. If it returns 0 it will reboot the ESP8266.

A typical reason for interception is to handle fatal errors, prompting for user
intervention or reporting and issuing long delays before rebooting.

###### [Contents](./README.md#contents)

### 2.3.5 The user_start callback

This callback runs each time the ESP8266 is reset. The callback should return
promptly, and any coroutines launched by it should terminate quickly. If the
callback launches coroutines which run forever there is a hazard described
below. Recommendations:

 1. Have coros quit rapidly.
 2. Start "run forever" coros elsewhere than ``user_start``.
 3. Start them on the first run only.

If you must start a run forever coro each time ``user_start`` runs consider
this. After an error which causes the ESP8266 to be rebooted the callback runs
again causing coroutines launched by the callback to be re-created. This will
cause the scheduler's task queue to grow, potentially without limit.

It should hence be designed to quit prior to an ESP8266 reboot (the MicroPython
asyncio subset has no way to kill a running coro). For internal use the
MQTTLink has an ``ExitGate`` instance ``exit_gate``. A continuously running
coroutine should use the ``exit_gate`` context manager and poll
``exit_gate.ending()``. If it returns ``True`` the coro should terminate. If it
needs to pause it should issue

```python
result = await mqtt_link.exit_gate.sleep(time)
```

and quit if result is ``False``.

See ``pbmqtt_test.py`` and the
[synchronisation primitives docs](https://github.com/peterhinch/micropython-async/blob/master/PRIMITIVES.md).

###### [Contents](./README.md#contents)

## 2.4 Application design

### 2.4.1 User coroutines

Where possible these should periodically yield to the scheduler with a nonzero
delay. An ``asyncio.sleep(secs)`` or ``aysncio.sleep_ms(ms)`` will reduce
competition with the bitbanging communications, minimising any impact on
throughput. Issue a zero delay (or ``yield``) only when a fast response is
required.

### 2.4.2 WiFi Link Behaviour

The implicit characteristics of radio links mean that WiFi is subject to
outages of arbitrary duration: RF interference may occur, or the unit may move
out of range of the access point.

In the event of a WiFi outage the ESP8266, running the umqtt library, may
respond in two ways. If a socket is blocking it may block forever; it will also
wait forever if a publication with qos == 1 has taken place and the MQTT
protocol is waiting on a PUBACK response. In this case the serial link will
time out and the ESP8266 will be rebooted. If a socket operation is not in
progress a WIFI_DOWN status will be sent to the Pyboard; if the outage is brief
WIFI_UP will be sent and operation will continue. Outages longer than the link
timeout will result in an ESP8266 reboot.

An implication of this behaviour is that publications with qos == 1 may not be
delivered if the WiFi fails and causes a reboot while waiting for the PUBACK.
In my view qos == 1 is not strictly achievable with the current umqtt library
over a WiFi link. On a reliable network it is effective.

The driver aims to keep the link to the broker open at all times. It does this
by sending MQTT pings to the broker: four pings are sent during the keepalive
time. If no response is achieved in this period the broker is presumed to have
failed or timed out. The ``NO_NET`` status is reported (to enable user action)
and the ESP8266 rebooted.

###### [Contents](./README.md#contents)

# 3. The ESP8266

To use the precompiled build, follow the instructions in 3.1 below. The
remainder of the ESP8266 documentation is for those wishing to modify the
ESP8266 code. Since the Pyboard and the ESP8266 communicate via GPIO pins the
UART/USB interface is available for debugging.

# 3.1 Installing the precompiled build

Erase the flash with  
``esptool.py erase_flash``  
Then, from the project directory, issue  
``esptool.py --port /dev/ttyUSB0 --baud 115200 write_flash --verify --flash_size=detect -fm dio 0 firmware-combined.bin``  
These args for the reference board may need amending for other hardware.

# 3.2 Files

In the precompiled build all modules are implemented as frozen bytecode. For
development purposes you may wish to run mqtt.py (or others) as regular source
files. The precompiled build's modules directory comprises the following:

 1. The uasyncio library.
 2. The umqtt.robust library.
 3. ``mqtt.py`` Main module.
 4. ``syncom.py`` Bitbanged communications driver.
 5. ``aswitch.py`` Module has a retriggerable delay class.
 6. ``asyn.py`` Synchronisation primitives.
 7. ``status_values.py`` Numeric status codes.

To conserve space unused drivers are removed from the project's ``modules``
directory, leaving the following standard files:

 1. ``ntptime.py``
 2. ``flashbdev.py``
 3. ``inisetup.py``
 4. ``_boot.py`` Optionally replaced by modified version.

The ``mqtt`` module needs to auto-start after a hard reset. This requires a
``main.py`` file. If the standard ``_boot.py`` is used you will need to create
the file as below and copy it to the filesystem:

```python
import mqtt
```

The modified ``_boot.py`` in this repository removes the need for this step
enabling the firmware image to be flashed to an erased flash chip. After boot
if ``main.py`` does not exist it is created in the filesystem.

###### [Contents](./README.md#contents)

# 3.3 Pinout

This is defined in mqtt.py (``Channel`` constructor). Pin 15 is used for mckout
because this has an on-board pull down resistor. This ensures that the ESP8266
clock line is zero while the host asserts Reset: at that time GPIO lines are
high impedance. If the pin lacks a pull down one should be supplied. A value of
10KΩ or thereabouts will suffice.

# 4. Mode of operation

This describes the basic mode of operation for anyone wishing to modify the
host or target code.

# 4.1 Communication

The host and target communicate by a symmetrical bidirectional serial protocol.
At the hardware level it is full-duplex, synchronous and independent of
processor speed. At the software level it is asynchronous. In this application
the unit of communication is a string. When a ``SynCom`` is instantiated it
does nothing until its asynchronous ``start`` method is launched. This takes a
coroutine as an argument. It waits for the other end of the link to start,
synchronises the interface and launches the coro.

This runs forever except - in the case of the host - on error. The host has a
means of issuing a hardware reset to the target. This is triggered by the coro
terminating. The ``SynCom`` instance resets the target, waits for synch, and
re-launches the coro (``SynCom`` start method).

The ESP8266 has no means of resetting the host, so there is no reason for its
coro (``main_task``) to end.

The interface also provides a means for the host to detect if the ESP8266 has
crashed or locked up. To process incoming messages it issues

```python
res = await channel.await_obj()
```

This will pause as long as necessary but a result of ``None`` means that the
channel has timed out which can be a result of ESP8266 failure. It can also
result from a socket blocking for longer than the link timeout. Normally
``res`` is a string.

###### [Contents](./README.md#contents)

# 4.2 Protocol

## 4.2.1 Initialisation

The host instantiates an ``MQTTlink`` object which creates a ``channel`` being
a ``SynCom`` instance. This issues the ``start`` method with its own ``start``
method as the coro argument. This will run every time the ESP8266 starts. When
it returns it causes an ESP8266 reset.

The host can send commands to the ESP8266 which replies with a status response.
The ESP8266 can also send unsolicited status messages. When a command is sent
the host waits for a response as described above, handling a ``None`` response.
The string is parsed into a command - typically 'status' - and an action, a
list of string arguments. In the case of 'status' messages the first of these
is the status value.

Status messages are first passed to the ``do_status`` method which performs
some basic housekeeping and provides optional 'verbose' print messages. It
returns the status value as an integer. It then waits on the asynchronous
method ``s_han`` which by default is ``default_status_handler``. This can be
overridden by the user.

Each time the ``start`` method runs it behaves as follows. If the user has set
up a will, it sends a ``will`` command to the ESP8266 and waits for a status
response.

Assuming success it then sends an ``init`` command with the ``INIT`` parameters
which causes the ESP8266 to connect to the WiFi network and then to the broker.
The initialisation phase ends when the ESP8266 sends a ``RUNNING`` status to
the host, when ``_running`` is set (by ``do_status``). In the meantime the
ESP8266 will send other status messages:

 1. ``DEFNET`` It is about to try the default network in its flash ROM.
 2. ``SPECNET`` It has failed to connect to this LAN and wants to connect to
 the one specified in ``INIT``. Unless the status handler has been overridden
 ``default_status_handler`` ensures this is done on the first boot only.
 3. ``BROKER_CHECK`` It is about to connect to the broker.
 4. ``BROKER_OK`` Broker connection established.

Once running it launches the user supplied coroutine. It also launches coros to
handle publications and to keep the broker alive with periodic MQTT pings:
``_ping()`` and ``_publish`` asynchronous methods. The initialisation phase is
now complete.

###### [Contents](./README.md#contents)

## 4.2.2 Running

This continuously running loop exits only on error when the ESP8266 is to be
rebooted. It waits on incoming messages from the ESP8266 (terminating on
``None``).

The ESP8266 can send various messages, some such as 'subs' asynchronously in
response to a subscription and others such as a 'PUBOK' status in response to
having processed a qos == 1 'publish' message from the host. Unsolicited
messages are:

 1. 'subs' A subscription was received.
 2. 'time',value The ESP8266 has contacted a timeserver and has this value.
 3. 'pingresp' The ESP8266 has pinged the broker and received a response.
 4. 'status', WIFI_UP
 5. 'status', WIFI_DOWN
 6. 'status', UNKNOWN This should never occur. ESP8266 has received an unknown
 command from the host.

Expected messages are:
 1. 'mem',free,allocated Response to a 'mem' command.
 2. 'status',PUBOK Response to a qos == 1 publication.

When a qos == 1 publication is issued the host's ``_publish`` asynchronous
method informs the ESP8266 and starts a timer. This locks out further
publications until a 'PUBOK' is received from the ESP8266. If the timer times
out, ``_running`` is set ``False`` prompting a reboot in the main loop. A
'PUBOK' stops the timer and re-enables publications which resume if any are
queued.

A publication with qos == 0 is sent to the ESP8266 but the timer is not started
and no response is expected.

###### [Contents](./README.md#contents)

# 5. Postscript

A few people have complemented me on my documentation. There are three reasons
why I aim to write decent documentation:

 1. I use and appreciate the good documentation of others.
 2. I enjoy writing it and it provides a reason for reviewing my code.
 3. A function of age. If I don't write it down and revisit a project after a
 few months I'm in a hole; baffled both by the code and by the overall design.
 My first reaction is "Gordon Bennett who wrote **this**?". This hit me with a
 vengeance after shelving this project last year :-)
