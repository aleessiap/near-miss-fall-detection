"""Wi-Fi connection of the fog node, with timeout and automatic reconnection."""

import time
import network

RETRY_S = 30        # Wi-Fi lost: new connection request every 30 s


class WiFiManager:

    def __init__(self, ssid, password):
        self._wlan = network.WLAN(network.STA_IF)
        self._ssid = ssid
        self._password = password
        self._last_request = None

    def _request(self):
        self._last_request = time.ticks_ms()
        try:
            self._wlan.active(True)
            self._wlan.connect(self._ssid, self._password)
        except OSError as e:            # e.g. a connection already in progress
            print('wifi: connection request:', e)

    def do_connect(self, timeout_s=30):
        """Connect at start-up. Returns True on success; on failure the main
        loop keeps asking for the connection (ensure_connected)."""
        self._wlan.active(True)
        if not self._wlan.isconnected():
            print('wifi: connecting to', self._ssid)
            self._request()
            t0 = time.ticks_ms()
            while not self._wlan.isconnected():
                if time.ticks_diff(time.ticks_ms(), t0) > timeout_s * 1000:
                    print('wifi: connection timeout')
                    return False
                time.sleep_ms(100)
        print('wifi: network config:', self._wlan.ifconfig())
        return True

    def ensure_connected(self):
        """True if connected; otherwise a new request at most every RETRY_S
        (non-blocking)."""
        if self._wlan.isconnected():
            return True
        if self._last_request is None or \
                time.ticks_diff(time.ticks_ms(), self._last_request) >= RETRY_S * 1000:
            print('wifi: not connected, connecting again')
            self._request()
        return False
