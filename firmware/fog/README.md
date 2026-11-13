# Fog node firmware

MicroPython firmware for the fog node: a stationary TinyS3 (ESP32-S3) installed on
site. It subscribes to the operators' topics on the edge-level MQTT broker, which
collects the events of all edge boards, and republishes every event, unchanged, on
the cloud-level broker under `<mqtt_topic_cloud>/<operator topic>`. No processing or
filtering is done; storage and the REST API belong to the Cloud layer.

## Behaviour

- The edge and cloud connections are independent. While the cloud broker is
  unreachable, received events are kept in a queue of up to 50 messages (the oldest
  is dropped when it is full) and forwarded, in order, when the connection returns.
- Socket operations have a 3 s timeout; reconnection attempts are spaced out (5 s
  doubling up to 60 s); the Wi-Fi connection is requested again every 30 s. The
  subscription is renewed at every reconnection to the edge broker.
- Events use QoS 0 and a clean session: events published while the fog node is
  disconnected from the edge broker are not kept by the broker.

## Configuration (`config.json`)

| key | meaning |
| --- | --- |
| `wifi_ssid`, `wifi_pass` | Wi-Fi network |
| `mqtt_broker`, `mqtt_port`, `mqtt_user`, `mqtt_password` | edge-level broker |
| `mqtt_client_id` | client id on both brokers |
| `mqtt_topic_operators` | topics of the edge boards (their `mqtt_topic`) |
| `cloud_mqtt_broker`, `cloud_mqtt_port`, `cloud_mqtt_user`, `cloud_mqtt_password` | cloud-level broker |
| `mqtt_topic_cloud` | prefix of the topics on the cloud broker (site identifier) |

## Files on the device

```text
/
├── boot.py               3 s pause at start-up (time to stop the firmware from Thonny)
├── main.py               start-up: reads the configuration and starts the bridge
├── config.json           Wi-Fi, edge-level and cloud-level brokers, topics
├── coroutines/mqtt.py    edge and cloud connections, event queue
└── lib/wifi_manager.py   Wi-Fi connection
```

The firmware needs MicroPython for ESP32-S3 with `umqtt.simple`. If it is not part
of the MicroPython build, install it from the computer with
`mpremote mip install umqtt.simple`, or on the board, once connected to Wi-Fi, with
`import mip; mip.install("umqtt.simple")`.

## Installation and use

1. In Thonny select the interpreter *MicroPython (ESP32)* and the port of the TinyS3.
2. Fill in `config.json`: Wi-Fi, address of the edge-level broker (the one set as
   `mqtt_broker` on the edge boards), their topics in `mqtt_topic_operators`, cloud
   broker and site prefix.
3. Copy the content of this folder to the root of the board (*View > Files*, select
   the files on the computer side, right click > *Upload to /*). Do not copy
   `README.md`.
4. Restart the board: the bridge starts by itself. To check the forwarding, watch the
   cloud broker with `mosquitto_sub -h <cloud broker> -t '<mqtt_topic_cloud>/#' -v`.
5. To work on the board from Thonny press *Stop*: the firmware stops and the REPL is
   available.

