from .wlan_base import BaseWLAN
import uasyncio as asyncio


class WLAN(BaseWLAN):
    def __init__(self, ssid, wifi_pw):
        super().__init__(ssid, wifi_pw)

    async def _connect(self):
        s = self._sta_if
        s.active(True)
        s.connect(self._ssid, self._wifi_pw)
        # Pyboard doesn't yet have STAT_CONNECTING constant
        while s.status() in (1, 2):
            await asyncio.sleep(1)

        return await self._check_reliability()
