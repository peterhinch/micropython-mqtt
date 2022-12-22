# A General MicroPython MQTT client

## Background

The `mqtt_as` module was an engineer's solution to a specific problem: bringing
resilient MQTT to ESP8266. It was readily ported to other WiFi platforms as
they became available. Kevin Köck planned to extend it to handle wired networks
but is unable to continue this work.

I have become convinced that, rather than extending to further network hardware,
a rewrite is called for. These notes detail the reasoning and provide an outline
of the requirements.

## Why a rewrite is needed

MQTT is designed to provide reliable communication over an unreliable point to
point link. It is not constrained to socket based communications. A client
should be able to use any radio or wired hardware. Notable candidates are
wired Ethernet, LoraWan, point-to-point Lora, or radios like NRF24L01. It
should be possible to add new communications modules to the basic client as
they become available. A modular design should keep the size of the client
module within bounds.

By contrast, `mqtt_as` is strictly socket-based.

## Client characteristics

### Asynchronous

It must be asynchronous because the MQTT protocol requires background tasks. An
MQTT ping packet must be sent to the broker if nothing has been received from
it for a period. Where a packet with `qos > 0` is sent to the broker, the client
must wait for a response and if none is received, re-transmit. This needs to be
handled by the client in a way which is largely transparent to the application.
The task performing transmission may pause until the protocol has completed, but
the application - with other MQTT operations - should continue to run.

In this context it is worth noting that latencies can be very long if a link
outage occurs part way through a handshake operation. Implications of this are
discussed in the `mqtt_as` docs.

### Resilient

The client needs to be able to handle and recover from link outages in a way
that preserves message integrity and is transparent to the application.
Currently this assumes a WiFi link: the process should be generalised.

Communication links can comprise many stages between the client and the broker.
An outage may be detected by the communications module or by the client. For
example the client may detect the lack of a ping response from the broker. This
provides no information on which link in the chain has failed. When an outage
is detected, the client should down communications for long enough that every
link in the chain "knows" the link is down. This "belt and braces"
approach ensures that the process of re-establishing the link always starts
from the same state.

The requirement for resilence over radio links implies a significant burden of
testing. Aside from complete outages, RSSI can vary unpredictably and bursts of
interference can occur. The case where the client platform is mobile should be
considered.

### Communication modules

Socket based solutions are likely to be based on two modules: a socket layer
and a transport layer. The latter would handle link outages. In the WiFi case
there is a procedure for downing and reinstating the link. This is likely to be
different in other cases (LoraWan, cellular). It's also worth nothing that the
socket layer needs to reflect minor differences between platforms.

In the case of point-to-point links, there is a need for gateway hardware. This
would be connected to a LAN and convert between packets on the radio and MQTT
messages exchanged with the broker.

### Possible enhancements

Support for `qos == 2` is reasonably straightforward. `mqtt_as` does not offer
this to save bytes on ESP8266. However, given that `mqtt_as` provides a
solution for that platform, a new driver might include this.

The MQTT protocol has been updated since `mqtt_as` was written. The
implications of this should be investigated.

The use of a `dict` to store MQTT parameters has been discussed in the past and
should be reviewed.
