"""Wi-Fi connection and clock synchronisation."""

import time
import network
from lib.console import log


class WiFiManager:
    """Connect to an access point, synchronise the clock, switch the radio off."""

    def __init__(self, ssid, password):
        self._wlan = network.WLAN(network.STA_IF)
        self._ssid = ssid
        self._password = password

    def _request(self):
        """Ask the access point for a connection. Returns True if the request
        was accepted.

        After a soft reset (Ctrl+D, or a new run from Thonny) a connection
        attempt of the previous run may still be in progress, and connect()
        fails with "Wifi Internal State Error": that attempt is stopped and
        the request repeated once.
        """
        try:
            self._wlan.connect(self._ssid, self._password)
            return True
        except OSError as e:
            log('wifi: %s, restarting the connection' % e)
        try:
            self._wlan.disconnect()
        except OSError:
            pass
        time.sleep_ms(500)
        try:
            self._wlan.connect(self._ssid, self._password)
            return True
        except OSError as e:
            log('wifi: connection request failed:', e)
            return False

    def do_connect(self, timeout_s=30):
        """Connect to the access point. Returns True on success; on failure the
        firmware goes on and the MQTT task asks for the connection again later."""
        self._wlan.active(True)
        if not self._wlan.isconnected():
            log('wifi: connecting to', self._ssid)
            if not self._request():
                return False
            t0 = time.ticks_ms()
            while not self._wlan.isconnected():
                if time.ticks_diff(time.ticks_ms(), t0) > timeout_s * 1000:
                    log('wifi: connection timeout')
                    return False
                time.sleep_ms(100)
        log('wifi: network config:', self._wlan.ifconfig())
        return True

    def disconnect(self):
        """Close the connection and switch the radio off."""
        try:
            self._wlan.disconnect()
        except OSError:
            pass
        self._wlan.active(False)

    def sync_RTC(self, host=None):
        """Set the clock with an NTP request (millisecond resolution,
        lib/clock_sync.py). Returns True on success."""
        from lib import clock_sync
        try:
            offset_ms, rtt_ms = clock_sync.sync(host or clock_sync.NTP_HOST)
        except Exception as e:
            log('wifi: clock not synchronised:', e)
            return False
        log('wifi: clock synchronised (round trip %.0f ms)' % rtt_ms)
        return True


def radio_off():
    """Switch off both Wi-Fi interfaces (station and access point)."""
    for iface in (network.STA_IF, network.AP_IF):
        try:
            network.WLAN(iface).active(False)
        except OSError:
            pass
