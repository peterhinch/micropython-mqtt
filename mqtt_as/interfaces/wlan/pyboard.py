from .. import BaseInterface
import network
import uasyncio as asyncio


class WLAN(BaseInterface):
    def __init__(self, ssid, wifi_pw):
        super().__init__()
        self.DEBUG = False
        self._ssid = ssid
        self._wifi_pw = wifi_pw
        # wifi credentials required for ESP32 / Pyboard D. Optional ESP8266
        self._sta_if = network.WLAN(network.STA_IF)
        self._sta_if.active(True)

    async def _connect(self):
        s = self._sta_if
        s.active(True)
        s.connect(self._ssid, self._wifi_pw)
        # Pyboard doesn't yet have STAT_CONNECTING constant
        while s.status() in (1, 2):
            await asyncio.sleep(1)

        if not s.isconnected():
            return False
        # Ensure connection stays up for a few secs.
        if self.DEBUG:
            print('Checking WiFi integrity.')
        for _ in range(5):
            if not s.isconnected():
                return False  # in 1st 5 secs
            await asyncio.sleep(1)
        if self.DEBUG:
            print('Got reliable connection')
        return True

    async def _disconnect(self):
        self._sta_if.disconnect()
        return True  # not checking if really disconnected.

    def _isconnected(self):
        return self._sta_if.isconnected()
