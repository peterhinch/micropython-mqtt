# common.py Common settings for all nodes
import network
import espnow
from ubinascii import unhexlify

# Adapt these two lines
gateway = unhexlify(b'2462abe6b0b4')  # ESP reference clone
channel = 3  # Router channe]

sta = network.WLAN(network.STA_IF); sta.active(False)
ap = network.WLAN(network.AP_IF); ap.active(False)
sta.active(True)
while not sta.active():
    time.sleep(0.1)
#if sys.platform == "esp8266":
    #sta.disconnect()
    #while sta.isconnected():
        #time.sleep(0.1)
sta.config(channel=channel)
sta.config(pm = sta.PM_NONE)  # No power management
sta.active(True)
espnow = espnow.ESPNow()  # Returns ESPNow object
espnow.active(True)
espnow.add_peer(gateway)
# TODO ping gateway. On fail, scan for it.
# Also need to ping and optionally scan after WiFi outage
