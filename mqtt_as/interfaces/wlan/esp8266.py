from .wlan_base import BaseWLAN
import network
import uasyncio as asyncio


class WLAN(BaseWLAN):
    def __init__(self, ssid=None, wifi_pw=None):
        super().__init__(ssid, wifi_pw)
        import esp
        esp.sleep_type(0)  # Improve connection integrity at cost of power consumption.

    async def _connect(self):
        s = self._sta_if
        if s.isconnected():  # 1st attempt, already connected.
            return True
        s.active(True)
        s.connect()  # ESP8266 remembers connection.
        for _ in range(60):
            if s.status() != network.STAT_CONNECTING:  # Break out on fail or success. Check once per sec.
                break
            await asyncio.sleep(1)
        if s.status() == network.STAT_CONNECTING:  # might hang forever awaiting dhcp lease renewal or something else
            s.disconnect()
            await asyncio.sleep(1)
        if not s.isconnected() and self._ssid is not None and self._wifi_pw is not None:
            s.connect(self._ssid, self._wifi_pw)
            while s.status() == network.STAT_CONNECTING:  # Break out on fail or success. Check once per sec.
                await asyncio.sleep(1)

        return await self._check_reliability()
