# Fog node firmware (TinyS3, ESP32-S3): MQTT bridge between the edge-level
# broker, which collects the events of the operators' edge boards, and the
# cloud-level broker. Events are forwarded unchanged (coroutines/mqtt.py).

import gc
import json
import sys
import uasyncio

from coroutines.mqtt import mqtt_coro
from lib.wifi_manager import WiFiManager

_CFG_FILENAME = "config.json"
_REQUIRED = ("wifi_ssid", "wifi_pass", "mqtt_broker", "mqtt_client_id",
             "mqtt_topic_operators", "cloud_mqtt_broker")


def load_config():
    try:
        with open(_CFG_FILENAME) as f:
            cfg = json.load(f)
    except Exception as e:
        print("main: error while reading config file:", e)
        sys.exit()
    missing = [k for k in _REQUIRED if k not in cfg]
    if missing:
        print("main: missing keys in config.json:", missing)
        sys.exit()
    return cfg


if __name__ == "__main__":
    gc.enable()
    cfg = load_config()
    wm = WiFiManager(cfg["wifi_ssid"], cfg["wifi_pass"])
    wm.do_connect()             # on failure the main loop keeps retrying
    try:
        uasyncio.run(mqtt_coro(cfg, wm))
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        uasyncio.new_event_loop()   # clear retained state
