# MQTT publishing.
#
# mqtt_task() publishes the messages put in the outgoing queue (one message
# per detected near-miss event). A ping is sent every PING_PERIOD_S so the
# broker keeps the connection open even when no event occurs for a long
# time; on any error the client reconnects.
#
# The network may go down for minutes or hours: nothing here may stop the
# rest of the firmware (acquisition, inference, logging) for long.
#   - Socket operations have a timeout (SOCKET_TIMEOUT_S), so a dead
#     connection raises an error instead of blocking.
#   - Reconnection attempts are spaced out, from RETRY_MIN_S up to
#     RETRY_MAX_S, so that failed attempts take a small fraction of the time.
#   - If the Wi-Fi connection is lost, no MQTT attempt is made; the Wi-Fi
#     connection is requested again every WIFI_RETRY_S.
#
# The device clock (used for the event times) is set with NTP at start-up and
# drifts by tens of ppm, about 0.15 s per hour on the test board. In the
# battery test modes that send messages (C, W, W1) it is synchronised again
# every CLOCK_RESYNC_S, so that the delivery latency measured on the PC
# (arrival time - event time) does not include the drift; the offset found at
# each synchronisation is written in the log ("# t_s=... CLOCK_SYNC
# offset_ms=... rtt_ms=..."). In normal operation the clock is set only at
# start-up.
#
# Only event messages are sent: raw IMU data never leave the device.

import time
import uasyncio as asyncio
from umqtt.simple import MQTTClient
import battery_test as bt
from lib import clock_sync
from lib.console import log

PING_PERIOD_S = 30
SOCKET_TIMEOUT_S = 3     # connect, publish and ping: error after 3 s instead of blocking
RETRY_MIN_S = 5          # first wait after a failed connection attempt
RETRY_MAX_S = 60         # the wait doubles after each failure, up to this value
WIFI_RETRY_S = 30        # Wi-Fi lost: new connection request every 30 s
# NTP synchronisation every 10 min in the battery test modes C, W, W1 (latency
# measurement); 0 = only at start-up (normal operation and the other modes)
CLOCK_RESYNC_S = 600 if bt.SIMULATED_EVENTS else 0
CLOCK_RETRY_S = 60       # failed synchronisation: new attempt after 1 min


class Publisher:
    """Thin wrapper around umqtt.simple with reconnection and counters."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.topic = cfg.get('mqtt_topic', 'tinys3/events')
        self.client = None
        self.last_activity = time.ticks_ms()
        self.retry_s = RETRY_MIN_S
        self.wifi_request = None     # ticks_ms of the last Wi-Fi connection request
        self.rtc_synced = bool(cfg.get('_rtc_synced'))   # clock set by NTP at start-up
        # ticks_ms of the next NTP synchronisation (None: none planned)
        self.next_sync = (time.ticks_add(time.ticks_ms(), CLOCK_RESYNC_S * 1000)
                          if self.rtc_synced and CLOCK_RESYNC_S else None)
        bt.set_info('clock_resync_s', CLOCK_RESYNC_S)

    def _set_timeout(self):
        try:
            self.client.sock.settimeout(SOCKET_TIMEOUT_S)
        except Exception:
            pass

    def connect(self):
        cfg = self.cfg
        client = MQTTClient(
            client_id=cfg['mqtt_client_id'],
            server=cfg['mqtt_broker'],
            port=cfg.get('mqtt_port', 1883),
            user=cfg.get('mqtt_user') or None,
            password=cfg.get('mqtt_password') or None,
            keepalive=60,
        )
        try:
            client.connect(timeout=SOCKET_TIMEOUT_S)
        except TypeError:
            # older umqtt.simple without the timeout argument
            client.connect()
        self.client = client
        self._set_timeout()
        self.last_activity = time.ticks_ms()
        log('mqtt: connected to broker')
        if not self.rtc_synced:
            # the Wi-Fi was not available at start-up: set the clock now
            self.sync_clock()

    def sync_clock(self):
        """Set the clock with NTP and plan the next synchronisation. Errors are
        only logged: the messages keep the current device time."""
        try:
            offset_ms, rtt_ms = clock_sync.sync(self.cfg.get('ntp_host', clock_sync.NTP_HOST))
        except Exception as e:
            log('mqtt: clock not synchronised:', e)
            bt.note('CLOCK_SYNC_FAILED')
            self.next_sync = time.ticks_add(time.ticks_ms(), CLOCK_RETRY_S * 1000)
            return
        if self.rtc_synced:
            # offset = drift since the previous synchronisation
            log('mqtt: clock synchronised, offset %.1f ms, round trip %.1f ms' % (offset_ms, rtt_ms))
            bt.note('CLOCK_SYNC offset_ms=%.1f rtt_ms=%.1f' % (offset_ms, rtt_ms))
        else:
            # first synchronisation: the clock was not set, the offset is meaningless
            log('mqtt: clock synchronised, round trip %.1f ms' % rtt_ms)
            bt.note('CLOCK_SYNC first rtt_ms=%.1f' % rtt_ms)
        self.rtc_synced = True
        self.next_sync = (time.ticks_add(time.ticks_ms(), CLOCK_RESYNC_S * 1000)
                          if CLOCK_RESYNC_S else None)

    def clock_due(self):
        """True if a planned NTP synchronisation is due."""
        return self.next_sync is not None and time.ticks_diff(time.ticks_ms(), self.next_sync) >= 0

    def wifi_connected(self):
        """True if the Wi-Fi is connected. If not, ask for a new connection
        (at most every WIFI_RETRY_S; the request returns immediately)."""
        import network
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            self.wifi_request = None
            return True
        now = time.ticks_ms()
        if self.wifi_request is None or time.ticks_diff(now, self.wifi_request) >= WIFI_RETRY_S * 1000:
            self.wifi_request = now
            bt.count('wifi_retries')
            log('mqtt: Wi-Fi not connected, connecting again')
            try:
                wlan.active(True)
                wlan.connect(self.cfg['wifi_ssid'], self.cfg['wifi_pass'])
            except Exception as e:      # e.g. a connection already in progress
                log('mqtt: Wi-Fi connection request:', e)
        return False

    def close(self):
        try:
            self.client.disconnect()
        except Exception:
            pass
        self.client = None

    def publish(self, topic, payload):
        """Publish one message; returns the payload size in bytes."""
        self.client.publish(topic, payload)
        self.last_activity = time.ticks_ms()
        bt.count('mqtt_bytes', len(payload))
        return len(payload)

    def keepalive(self):
        """Ping the broker if nothing was sent for PING_PERIOD_S and read any
        pending reply (PINGRESP) so the socket buffer does not fill up."""
        if time.ticks_diff(time.ticks_ms(), self.last_activity) >= PING_PERIOD_S * 1000:
            self.client.ping()
            self.last_activity = time.ticks_ms()
        self.client.check_msg()
        self._set_timeout()     # check_msg() leaves the socket in blocking mode

    async def ensure_connected(self):
        while self.client is None:
            if not self.wifi_connected():
                await asyncio.sleep(1)
                continue
            try:
                self.connect()
                self.retry_s = RETRY_MIN_S
            except Exception as e:
                log('mqtt: connection error:', e)
                self.client = None
                bt.count('mqtt_errors')
                await asyncio.sleep(self.retry_s)
                self.retry_s = min(self.retry_s * 2, RETRY_MAX_S)

    def failed(self, e):
        log('mqtt: error:', e)
        bt.count('mqtt_errors')
        bt.count('mqtt_reconnects')
        self.close()


async def mqtt_task(outgoing_queue, publisher):
    """Publish every message of the outgoing queue as JSON.

    A message leaves the queue only after publish() returns: if publishing
    raises, it stays first in the queue and is sent after the reconnection.
    With QoS 0 a message written to a connection that has silently died is
    still lost; the loss is detected only by the next socket error.
    """
    from coroutines.machine_learning_inference import payload
    while True:
        await publisher.ensure_connected()
        try:
            while not outgoing_queue.empty():
                rec = outgoing_queue.peek()
                data = payload(rec)
                publisher.publish(publisher.topic, data)
                outgoing_queue.get_nowait()
                if 'simulated' in rec['eventType']:
                    bt.count('sim_events')      # simulated messages (events or windows)
                else:
                    bt.count('events')
                log('mqtt: published', data)
            publisher.keepalive()
        except Exception as e:
            publisher.failed(e)
        # only when the queue is empty, so that no message waits for the NTP
        # request (at most TIMEOUT_S of lib/clock_sync.py)
        if publisher.client is not None and outgoing_queue.empty() and publisher.clock_due():
            publisher.sync_clock()
        await asyncio.sleep_ms(100)


async def simulated_event_task(outgoing_queue, sensor_id, cfg):
    """Battery test modes C, W, W1: controlled message traffic.

    Every SIMULATED_EVENT_PERIOD_S a near-miss of n adjacent windows starts
    (n taken in turn from SIMULATED_WINDOWS) and the messages are sent when the
    real system would send them:
      C   one event message, at the first window after the event (n + 1 s
          after its start), as the event rule does;
      W   one message per window, at the end of each window (1, 2, ... n s).
      W1  a near-miss in every window: one window message every second.
    Messages follow the same path as real ones (queue, MQTT task). Nothing is
    sent before the test starts (board charging on USB) or after it ends.
    """
    from coroutines.machine_learning_inference import event_message, window_message, enqueue
    window_ms = int(cfg.get('WINDOW_MS', 2000))
    step_ms = int(cfg.get('STEP_MS', 1000))
    if bt.CONTINUOUS_NEAR_MISS:
        while True:
            await asyncio.sleep_ms(step_ms)
            if not bt.running():
                continue
            enqueue(outgoing_queue, window_message(time.ticks_ms(), window_ms, sensor_id,
                                                   'near_miss_window_simulated'))
    period_ms = bt.SIMULATED_EVENT_PERIOD_S * 1000
    t_next = time.ticks_add(time.ticks_ms(), period_ms)
    k = 0
    while True:
        if not bt.running():
            # before the test starts: the first event comes one period after the start
            await asyncio.sleep_ms(200)
            t_next = time.ticks_add(time.ticks_ms(), period_ms)
            continue
        # events start at fixed times (one every period), whatever their length
        wait = time.ticks_diff(t_next, time.ticks_ms())
        if wait > 0:
            await asyncio.sleep_ms(wait)
        start = time.ticks_ms()
        t_next = time.ticks_add(t_next, period_ms)
        n = bt.SIMULATED_WINDOWS[k % len(bt.SIMULATED_WINDOWS)]
        k += 1
        if bt.PER_WINDOW_MESSAGES:
            for _ in range(n):
                await asyncio.sleep_ms(step_ms)
                if bt.running():
                    enqueue(outgoing_queue, window_message(time.ticks_ms(), window_ms, sensor_id,
                                                           'near_miss_window_simulated'))
        else:
            await asyncio.sleep_ms((n + 1) * step_ms)
            # n adjacent windows: from the start of the first to the end of the last
            end = time.ticks_add(start, window_ms + (n - 1) * step_ms)
            event = {'start': start, 'end': end, 'windows': n}
            if bt.running():
                enqueue(outgoing_queue, event_message(event, sensor_id, 'near_miss_simulated'))
