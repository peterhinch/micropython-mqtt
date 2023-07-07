# common.py Common settings for all nodes

# (C) Copyright Peter Hinch 2023
# Released under the MIT licence.

# scan and set_channel functions written by Glenn Moloney @glenn20
# micropython-espnow-utils:
# https://github.com/glenn20/micropython-espnow-utils/tree/main

import network
import espnow
from ubinascii import unhexlify
import json
import sys

# Adapt these two lines
gateway = unhexlify(b'2462abe6b0b5')  # ESP reference clone AP I/F
#gateway = unhexlify(b'2462abe6b0b4')  # ESP reference clone Sta I/F
channel = 3  # Router channel or None to scan


def set_channel(channel):
    if sta.isconnected():
        raise OSError("can not set channel when connected to wifi network.")
    if ap.isconnected():
        raise OSError("can not set channel when clients are connected to AP.")
    if sta.active() and sys.platform != "esp8266":
        sta.config(channel=channel)  # On ESP32 use STA interface FAIL with RuntimeError: Wifi Unknown Error 0x0102
        return sta.config("channel")
    else:
        # On ESP8266, use the AP interface to set the channel of the STA interface
        ap_save = ap.active()
        ap.active(True)
        ap.config(channel=channel)
        ap.active(ap_save)
        return ap.config("channel")


def scan(peer, retries=5):
    """Scan the wifi channels to find the given espnow peer device.

    If the peer is found, the channel will be printed and the channel number
    returned.
    Will:
        - scan using the STA_IF;
        - turn off the AP_IF when finished (on esp8266); and
        - leave the STA_IF running on the selected channel of the peer.

    Args:
        peer (bytes): The MAC address of the peer device to find.
        retries (int, optional):
            Number of times to attempt to send for each channel. Defaults to 5.

    Returns:
        int: The channel number of the peer (or 0 if not found)
    """
    enow = espnow.ESPNow()
    enow.active(True)
    try:
        enow.add_peer(peer)  # If user has not already registered peer
    except OSError:
        pass
    found = []
    for channel in range(1, 15):
        set_channel(channel)
        for _ in range(retries):
            if enow.send(peer, b'ping'):
                found.append(channel)
                print(f"Found peer {peer} on channel {channel}.")
                break
                # return channel
    if not found:
        return 0
    # Because of channel cross-talk we expect more than one channel to be found
    # If 3 channels found, select the middle one
    # If 2 channels found: select first one if it is channel 1 else second
    # If 1 channels found, select it
    count = len(found)
    index = 0 if count == 1 or (count == 2 and found[0] == 1) else 1
    channel = found[index]
    print(f"Setting wifi channel to {channel}")
    set_channel(channel)
    return channel

sta = network.WLAN(network.STA_IF); sta.active(False)
ap = network.WLAN(network.AP_IF); ap.active(False)
sta.active(True)
while not sta.active():
    time.sleep(0.1)
if sys.platform == "esp8266":
    sta.disconnect()
    while sta.isconnected():
        time.sleep(0.1)
    ap.active(True)
    if channel is None:
        scan(gateway)
    else:
        ap.config(channel=channel)
    ap.config(pm = sta.PM_NONE)  # No power management
    ap.active(True)
else:
    if channel is None:
        scan(gateway)
    else:
        sta.config(channel=channel)
    sta.config(pm = sta.PM_NONE)  # No power management
    sta.active(True)
espnow = espnow.ESPNow()  # Returns ESPNow object
espnow.active(True)
espnow.add_peer(gateway)  # ESP8266 FAIL here if channel was set by scanning.
def subscribe(topic, qos):
    espnow.send(gateway, json.dumps([topic, qos]))
# TODO ping gateway. On fail, scan for it.
# Also need to ping and optionally scan after WiFi outage

