# Firmware

This repository contains the embedded software stack for a real-time near-miss fall detection system.

The system acquires inertial data from a wearable IMU via Bluetooth Low Energy, performs on-device signal preprocessing and machine learning inference, and publishes detection events to an MQTT broker. A fog layer node subscribes to those events and forwards them to a cloud API.

---

## Repository Structure

```text
├── edge/                        # MicroPython firmware for the TinyS3 wearable
│   ├── main.py
│   ├── boot.py
│   ├── config.json
│   ├── coroutines/              # Async tasks (BLE, preprocessing, inference, MQTT)
│   │   ├── bluetooth_handler.py
│   │   ├── data_processor.py
│   │   ├── machine_learning_inference.py
│   │   ├── mqtt.py
│   │   ├── preprocessor.py
│   │   └── save_data.py
│   └── lib/                     # Libraries (model, buffer, sensors, BLE, WiFi)
│       ├── aioble/              # Async BLE library
│       ├── peripherals/         # Hardware peripherals (LED)
│       ├── primitives/          # Async primitives (Queue)
│       ├── constants.py
│       ├── model.py
│       ├── scaler_values.py
│       ├── Sensor_dimension.py
│       ├── wifi_manager.py
│       ├── windowedCircularBuffer.py
│       └── xgb_model.mpy
├── fog/                         # MicroPython firmware for the fog node
│   ├── main.py
│   ├── boot.py
│   ├── config.json
│   ├── coroutines/              # MQTT subscriber + cloud forwarding
│   └── lib/                     # WiFi manager
├── test-mqtt-broker/            # Local MQTT broker for development and testing
│   ├── docker-compose.yaml
│   └── mosquitto/config/
└── README.md
```

---

## Edge Node (`edge/`)

Runs on a TinyS3 (ESP32-S3) microcontroller programmed in MicroPython.

### Runtime pipeline

1. Connects to the IMU sensor over BLE using `aioble`
2. Reads raw inertial data (accelerometer, gyroscope, magnetometer, orientation angles) from BLE notifications
3. Feeds data into a windowed circular buffer (`WindowedCircularBuffer`) per sensor dimension
4. Extracts 90 statistical features per window (mean, std, variance, range, IQR, energy, SMA, skewness, kurtosis, correlation, covariance)
5. Scales features and runs inference with the embedded XGBoost model
6. If a near-miss is detected, publishes a JSON event to the MQTT broker

### Operating modes

Controlled via `config.json`:

- **Inference mode** (`register_data_mode: false`) — runs the full preprocessing → ML → MQTT pipeline
- **Data collection mode** (`register_data_mode: true`) — saves raw sensor readings to a JSON file on the device for offline analysis

### Key files

| File | Description |
|---|---|
| `coroutines/data_processor.py` | BLE notification reader and IMU decoder |
| `coroutines/preprocessor.py` | Windowed feature extraction per sensor channel |
| `coroutines/machine_learning_inference.py` | Builds the 90-feature vector and runs `model.predict()` |
| `coroutines/mqtt.py` | Publishes detection events to the MQTT broker |
| `coroutines/save_data.py` | Writes raw samples to JSON (data collection mode) |
| `lib/windowedCircularBuffer.py` | Time-windowed circular buffer with statistical methods |
| `lib/Sensor_dimension.py` | Per-channel wrapper exposing all statistical features |
| `lib/model.py` | Standard-scaling + XGBoost inference entry point |
| `lib/xgb_model.mpy` | Embedded XGBoost decision trees, pre-compiled to MicroPython bytecode |
| `lib/scaler_values.py` | Per-feature mean and std used for standard scaling |

### Configuration (`config.json`)

```json
{
    "wifi_ssid": "<WiFi network name>",
    "wifi_pass": "<WiFi password>",
    "IMU_SERVICE": "<BLE service UUID>",
    "IMU_CHAR_READ": "<BLE characteristic UUID>",
    "IMU_CHAR_WRITE": "<BLE characteristic UUID>",
    "IMU_MAC_ADDRESS": "<sensor MAC address>",
    "WINDOW_SIZE": 2,              // size of the sliding window in seconds
    "register_data_mode": false,
    "data_to_analyze": ["AccX", "AccY", "AccZ", ...],
    "mqtt_broker": "<broker IP or hostname>",
    "mqtt_port": 1883,
    "mqtt_client_id": "<worker identifier>",
    "mqtt_topic": "<topic for this worker>",
    "mqtt_user": "<mqtt username, leave empty if not required>",
    "mqtt_password": "<mqtt password, leave empty if not required>"
}
```

---

## Fog Layer (`fog/`)

Runs on a secondary MicroPython node (e.g., Raspberry Pi Pico W or another ESP32).

Subscribes to one or more MQTT topics published by the primary devices, processes incoming near-miss events, and forwards them to a cloud REST API via HTTP POST.

### Configuration (`config.json`)

```json
{
    "wifi_ssid": "<WiFi network name>",
    "wifi_pass": "<WiFi password>",
    "mqtt_broker": "<broker IP or hostname>",
    "mqtt_port": 1883,
    "mqtt_client_id": "<fog node identifier>",
    "mqtt_topic_operators": ["<topic of operator 1>", "<topic of operator 2>"],
    "mqtt_topic_cloud": "<topic of the workplace>",
    "mqtt_user": "<mqtt username, leave empty if not required>",
    "mqtt_password": "<mqtt password, leave empty if not required>",
    "api_token": "<cloud API token>",
    "cloud_api": "<cloud endpoint URL>"
}
```

---

## MQTT Broker (`test-mqtt-broker/`)

A Dockerized Eclipse Mosquitto instance for local development and testing.

```bash
docker compose up -d
```

Exposes:

- Port `1883` — standard MQTT
- Port `9001` — MQTT over WebSockets

Anonymous connections are allowed. Replace with a secured broker for production deployments.

---

## Hardware

- **Wearable node** — ESP32-S3 TinyS3
- **IMU sensor** — WT9011DCL-BT50 (BLE, 9-axis IMU + magnetometer)

Sensor placement: sacral region.

---

## MQTT Event Format

Events published by the primary device on a near-miss detection:

```json
{
    "eventType": "near_miss",
    "timestamp": 1234567890,
    "sensorId": "workers2"
}
```
