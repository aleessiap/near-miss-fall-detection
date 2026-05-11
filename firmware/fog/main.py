import gc
import json
import sys
import uasyncio

from coroutines.mqtt import mqtt_coro
from lib.wifi_manager import WiFiManager

# Configuration file
_CFG_FILENAME = "config.json"

async def main_loop(cfg_dict: dict):
    coro_handles = []

    # Start the MQTT coroutine to handle incoming MQTT messages and send data to the cloud API
    mqtt_handle = uasyncio.create_task(mqtt_coro(
        cfg=cfg_dict
    ))
    coro_handles.append(mqtt_handle)

    await uasyncio.Event().wait()

if __name__ == "__main__":
    # Enable garbage collector
    gc.enable()

    # Load configuration file
    cfg = {}

    try:
        with open(_CFG_FILENAME, 'r') as cfg_fp:
            cfg = json.load(cfg_fp)
            print("main: loaded config:\n", cfg)
    except:
        print("main: error while reading config file")
        sys.exit()

    # Establish WiFi connection and RTC sync
    print("Connecting to WiFi and synchronizing RTC...")
    wm = WiFiManager(cfg["wifi_ssid"], cfg["wifi_pass"])
    wm.do_connect()
    wm.sync_RTC()

    # Run the control task
    try:
        uasyncio.run(main_loop(cfg_dict=cfg))

    except KeyboardInterrupt:
        print('Interrupted')

    finally:
        uasyncio.new_event_loop()  # Clear retained state


    