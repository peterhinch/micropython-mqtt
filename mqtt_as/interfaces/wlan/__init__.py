from sys import platform

if platform == "esp8266":
    from .esp8266 import WLAN
elif platform == "esp32":
    from .esp32 import WLAN
elif platform == "pyboard":
    from .pyboard import WLAN
else:
    # just try esp32 implementation. Seems most mature.
    from .esp32 import WLAN
