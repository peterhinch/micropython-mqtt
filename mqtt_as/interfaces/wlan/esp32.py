from .wlan_base import BaseWLAN
import network
import uasyncio as asyncio


class WLAN(BaseWLAN):
    def __init__(self, ssid, wifi_pw):
        super().__init__(ssid, wifi_pw)
        # https://forum.micropython.org/viewtopic.php?f=16&t=3608&p=20942#p20942
        self.BUSY_ERRORS += [118, 119]  # Add in weird ESP32 errors

    async def _connect(self):
        s = self._sta_if
        while s.status() == network.STAT_CONNECTING:  # Break out on fail or success. Check once per sec.
            await asyncio.sleep(1)

        return await self._check_reliability()
