# MQTT bridge of the fog node.
#
# The fog node subscribes to the operators' topics on the edge-level broker
# and republishes every event, unchanged, on the cloud-level broker under
# "<mqtt_topic_cloud>/<operator topic>". No processing or filtering is done.
#
# Robustness:
#   - the two connections are independent: if the cloud side is down,
#     received events are kept in a bounded queue (MAX_PENDING, oldest
#     dropped and counted) and forwarded when it is back;
#   - socket operations have a timeout and reconnections are spaced out
#     (RETRY_MIN_S doubling up to RETRY_MAX_S), so a broker that is down
#     never blocks the node;
#   - the edge subscription is renewed at every reconnection.

import time
import uasyncio as asyncio
from umqtt.simple import MQTTClient

PING_PERIOD_S = 30
SOCKET_TIMEOUT_S = 3
RETRY_MIN_S = 5
RETRY_MAX_S = 60
MAX_PENDING = 50


def log(*args):
    print(*args)


class Link:
    """One MQTT connection with timeout, back-off and keepalive."""

    def __init__(self, name, client_id, server, port, user, password, on_connect=None):
        self.name = name
        self.args = dict(client_id=client_id, server=server, port=port,
                         user=user or None, password=password or None, keepalive=60)
        self.on_connect = on_connect
        self.client = None
        self.callback = None
        self.retry_s = RETRY_MIN_S
        self.next_try = time.ticks_ms()
        self.last_activity = time.ticks_ms()

    def _set_timeout(self):
        try:
            self.client.sock.settimeout(SOCKET_TIMEOUT_S)
        except Exception:
            pass

    def connected(self):
        """Connect if needed and allowed by the back-off; True if connected."""
        if self.client is not None:
            return True
        if time.ticks_diff(time.ticks_ms(), self.next_try) < 0:
            return False
        client = MQTTClient(**self.args)
        if self.callback is not None:
            client.set_callback(self.callback)
        try:
            try:
                client.connect(timeout=SOCKET_TIMEOUT_S)
            except TypeError:               # older umqtt.simple
                client.connect()
            self.client = client
            self._set_timeout()
            if self.on_connect is not None:
                self.on_connect(client)
        except Exception as e:
            log('fog: %s broker, connection error:' % self.name, e)
            self.client = None
            self.next_try = time.ticks_add(time.ticks_ms(), self.retry_s * 1000)
            self.retry_s = min(self.retry_s * 2, RETRY_MAX_S)
            return False
        self.retry_s = RETRY_MIN_S
        self.last_activity = time.ticks_ms()
        log('fog: %s broker connected' % self.name)
        return True

    def failed(self, e):
        log('fog: %s broker error:' % self.name, e)
        try:
            self.client.disconnect()
        except Exception:
            pass
        self.client = None
        self.next_try = time.ticks_add(time.ticks_ms(), self.retry_s * 1000)

    def keepalive(self):
        if time.ticks_diff(time.ticks_ms(), self.last_activity) >= PING_PERIOD_S * 1000:
            self.client.ping()
            self.last_activity = time.ticks_ms()


class Bridge:

    def __init__(self, cfg):
        self.topics = cfg.get('mqtt_topic_operators', [])
        self.prefix = cfg.get('mqtt_topic_cloud', 'workplace_1')
        self.pending = []           # (cloud topic, payload) waiting for the cloud side
        self.forwarded = 0
        self.dropped = 0
        self.edge = Link('edge', cfg['mqtt_client_id'], cfg['mqtt_broker'],
                         cfg.get('mqtt_port', 1883), cfg.get('mqtt_user'),
                         cfg.get('mqtt_password'), on_connect=self._subscribe)
        self.edge.callback = self._received
        self.cloud = Link('cloud', cfg['mqtt_client_id'], cfg['cloud_mqtt_broker'],
                          cfg.get('cloud_mqtt_port', 1883), cfg.get('cloud_mqtt_user'),
                          cfg.get('cloud_mqtt_password'))
        self.cloud.callback = lambda topic, msg: None    # no subscriptions on the cloud side

    def _subscribe(self, client):
        for topic in self.topics:
            client.subscribe(topic.encode())
            log('fog: subscribed to', topic)

    def _received(self, topic, msg):
        """Edge callback: queue the event for the cloud, payload unchanged."""
        if len(self.pending) >= MAX_PENDING:
            self.pending.pop(0)
            self.dropped += 1
            log('fog: queue full, oldest event dropped (%d so far)' % self.dropped)
        self.pending.append((self.prefix + '/' + topic.decode(), msg))
        # received packets do not count for the MQTT keepalive: only sent
        # packets do, so last_activity is not updated here

    def poll_edge(self):
        if not self.edge.connected():
            return
        try:
            self.edge.client.check_msg()
            self.edge._set_timeout()        # check_msg() leaves the socket blocking
            self.edge.keepalive()
        except Exception as e:
            self.edge.failed(e)

    def flush_cloud(self):
        if not self.cloud.connected():
            return
        try:
            while self.pending:
                topic, payload = self.pending[0]
                self.cloud.client.publish(topic, payload)
                self.pending.pop(0)         # removed only once published
                self.forwarded += 1
                self.cloud.last_activity = time.ticks_ms()
                log('fog: forwarded to', topic, payload)
            self.cloud.keepalive()
            # read the broker replies (PINGRESP) so the socket buffer does not fill up
            self.cloud.client.check_msg()
            self.cloud._set_timeout()
        except Exception as e:
            self.cloud.failed(e)


async def mqtt_coro(cfg, wifi):
    """Main loop of the fog node. ``wifi`` is a WiFiManager: while the Wi-Fi
    is down no MQTT operation is attempted."""
    bridge = Bridge(cfg)
    while True:
        if wifi.ensure_connected():
            bridge.poll_edge()
            bridge.flush_cloud()
        await asyncio.sleep_ms(100)
