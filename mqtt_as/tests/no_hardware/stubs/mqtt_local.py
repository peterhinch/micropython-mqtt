# tests/no_hardware/stubs/mqtt_local.py
#
# Stand-in for the device-specific mqtt_local.py that tests/v3/test.py,
# tests/v3/target.py, tests/v5/test.py and tests/v5/target.py import
# unmodified. Provides the same three names against the public
# test.mosquitto.org broker instead of real hardware/Wi-Fi.

import mqtt_as

config = mqtt_as.config.copy()
config.update(
    server="test.mosquitto.org",
    port=1883,
    ssid="dummy",  # Unused: the network.WLAN stub reports "always connected".
    wifi_pw="dummy",
)


def wifi_led(state):
    pass


def blue_led(state):
    pass
