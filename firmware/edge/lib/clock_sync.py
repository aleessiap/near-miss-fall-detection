"""Clock synchronisation with millisecond resolution (SNTP).

ntptime.settime() of MicroPython keeps only the whole seconds of the server
time (the fraction of the second is set to 0), so after it the device clock
can be up to 1 s behind. sync() keeps the fraction of the second and adds half
of the round-trip time of the request, so the error is at most half the
round-trip time (a few ms on a local network).

sync() also returns the offset of the device clock before the correction:
called periodically, it measures how far the clock drifts between two
synchronisations.
"""

import socket
import struct
import time
import machine

NTP_HOST = 'pool.ntp.org'
NTP_PORT = 123
TIMEOUT_S = 1
# Seconds from the NTP epoch (1900) to the epoch of time.time() (2000 on the
# ESP32 port of MicroPython, 1970 on some other ports).
_EPOCH_DELTA = 3155673600 if time.gmtime(0)[0] == 2000 else 2208988800


def sync(host=NTP_HOST):
    """Set the device clock from an NTP server.

    Returns (offset_ms, rtt_ms):
      offset_ms  server time - device time just before the correction
                 (positive: the device clock was behind);
      rtt_ms     round-trip time of the request.
    Raises OSError on network errors (no reply within TIMEOUT_S, DNS error).
    """
    addr = socket.getaddrinfo(host, NTP_PORT)[0][-1]
    query = bytearray(48)
    query[0] = 0x1B                  # leap indicator 0, version 3, mode 3 (client)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(TIMEOUT_S)
        t_send = time.ticks_us()
        s.sendto(query, addr)
        msg = s.recv(48)
        t_recv = time.ticks_us()
    finally:
        s.close()
    if len(msg) < 48:
        raise OSError('NTP reply too short')
    # transmit timestamp of the server: whole seconds and fraction (1/2**32 s)
    sec, frac = struct.unpack('!II', msg[40:48])
    if sec == 0:
        raise OSError('NTP reply without time')
    rtt_us = time.ticks_diff(t_recv, t_send)
    # Server time at the moment the reply arrived: the reply left the server
    # about half a round trip earlier (the server processing time is
    # negligible, a few us).
    server_us = (sec - _EPOCH_DELTA) * 1000000 + ((frac * 1000000) >> 32) + rtt_us // 2
    # Device time at the same moment, read before the clock is changed.
    device_us = time.time_ns() // 1000 - time.ticks_diff(time.ticks_us(), t_recv)
    # New time: server time plus the time elapsed since the reply arrived.
    now_us = server_us + time.ticks_diff(time.ticks_us(), t_recv)
    tm = time.gmtime(now_us // 1000000)
    # RTC.datetime: (year, month, day, weekday, hours, minutes, seconds,
    # microseconds) on the ESP32 port, as used by ntptime.settime().
    machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5],
                            now_us % 1000000))
    return (server_us - device_us) / 1000, rtt_us / 1000
