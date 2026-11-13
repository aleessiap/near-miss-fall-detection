# Firmware

<p align="center">
  <img src="https://img.shields.io/badge/MicroPython-2B2728?style=for-the-badge&logo=micropython&logoColor=white" alt="MicroPython">
  <img src="https://img.shields.io/badge/XGBoost-337AB7?style=for-the-badge&logo=xgboost&logoColor=white" alt="XGBoost">
  <img src="https://img.shields.io/badge/MQTT-660066?style=for-the-badge&logo=mqtt&logoColor=white" alt="MQTT">
  <img src="https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/ESP32-E7352C?style=for-the-badge&logo=espressif&logoColor=white" alt="ESP32">
</p>

---

## Table of Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Edge Node](#edge-node-edge)
- [Fog Layer](#fog-layer-fog)
- [MQTT Broker](#mqtt-broker-test-mqtt-broker)
- [Hardware](#hardware)
- [MQTT Event Format](#mqtt-event-format)

---

## Overview

This folder contains the embedded software stack for a real-time near-miss fall detection system, described in *An Edge AI Wearable System for Near-Miss Fall Detection*.

The system acquires inertial data from a wearable IMU via Bluetooth Low Energy, performs on-device signal preprocessing and machine learning inference, and publishes one event message per detected near-miss to an MQTT broker. A fog layer node subscribes to those events and forwards them to a cloud-level MQTT broker. Raw IMU data never leave the wearable device.

## Repository Structure

```text
├── edge/                        # MicroPython firmware for the TinyS3 wearable
│   ├── main.py
│   ├── boot.py
│   ├── config.json
│   ├── battery_test.py          # Measurement modes (MODE = None for normal operation)
│   ├── tinys3.py                # TinyS3 helper library (LED, battery voltage, USB detection)
│   ├── coroutines/              # Async tasks (BLE, acquisition, preprocessing, inference, MQTT)
│   │   ├── bluetooth_handler.py
│   │   ├── data_processor.py
│   │   ├── machine_learning_inference.py
│   │   ├── mqtt.py
│   │   ├── preprocessor.py
│   │   └── save_data.py
│   ├── lib/                     # Libraries (model, buffer, features, BLE, WiFi)
│   │   ├── aioble/              # Async BLE library
│   │   ├── peripherals/         # Hardware peripherals (LED)
│   │   ├── primitives/          # Async primitives (Queue)
│   │   ├── clock_sync.py
│   │   ├── console.py
│   │   ├── model_device.py
│   │   ├── model_device.bin
│   │   ├── model_input_array.py
│   │   ├── sample_buffer.py
│   │   ├── wifi_manager.py
│   │   └── window_features.py
│   └── README.md
├── fog/                         # MicroPython firmware for the fog node
│   ├── main.py
│   ├── boot.py
│   ├── config.json
│   ├── coroutines/              # MQTT bridge (edge-level broker → cloud-level broker)
│   ├── lib/                     # WiFi manager
│   └── README.md
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
2. Reads inertial data (acceleration, angular velocity, Euler angles) from the IMU
3. Computes the vector magnitudes and stores every sample in a ring buffer (`SampleBuffer`)
4. Every second, takes the last 2 s window and computes the features required by the model (53 features selected from statistics such as mean, median, std, variance, min, max, range, percentiles, IQR, energy, SMA, skewness, kurtosis, derivative, correlation, covariance)
5. Scales the features and runs inference with the embedded XGBoost model
6. Merges consecutive near-miss windows into one event and, when the event ends, publishes a JSON message to the MQTT broker

### Operating modes

Controlled via `config.json` and `battery_test.py`:

- **Inference mode** (`register_data_mode: false`) — runs the full preprocessing → ML → MQTT pipeline
- **Data collection mode** (`register_data_mode: true`) — saves raw sensor readings to a JSON file on the device for offline analysis
- **Measurement modes** (`MODE` in `battery_test.py`) — switch parts of the firmware on and off to measure their power consumption

### Key files

| File | Description |
|---|---|
| `coroutines/data_processor.py` | BLE acquisition and IMU decoder (3.5 Hz and 100 Hz modes) |
| `coroutines/preprocessor.py` | Vector magnitudes and buffering of each sample |
| `coroutines/machine_learning_inference.py` | Windowing, inference with `model.predict()` and event detection |
| `coroutines/mqtt.py` | Publishes event messages to the MQTT broker, with reconnection |
| `coroutines/save_data.py` | Writes raw samples to JSON (data collection mode) |
| `lib/sample_buffer.py` | Ring buffer of time-stamped multichannel samples |
| `lib/window_features.py` | Statistical features of one window, as in the training pipeline |
| `lib/model_device.py` | Standard scaling + XGBoost inference entry point |
| `lib/model_device.bin` | Embedded XGBoost decision trees |
| `lib/model_input_array.py` | Feature vector in the order expected by the model |

### Configuration (`config.json`)

```json
{
    "wifi_ssid": "<WiFi network name>",
    "wifi_pass": "<WiFi password>",
    "IMU_SERVICE": "<BLE service UUID>",
    "IMU_CHAR_READ": "<BLE characteristic UUID>",
    "IMU_CHAR_WRITE": "<BLE characteristic UUID>",
    "IMU_MAC_ADDRESS": "<sensor MAC address>",
    "ACQUISITION_MODE": "3.5Hz",
    "SAMPLING_RATE_HZ": 3.5,
    "SAMPLE_PERIOD_MS": 284,
    "WINDOW_MS": 2000,
    "STEP_MS": 1000,
    "MIN_WINDOW_SAMPLES": 2,
    "SENSOR_PERIOD_MS": 10.0716,
    "SENSOR_CLOCK_RELAX_MS": 0.02,
    "register_data_mode": false,
    "DEBUG_WINDOWS": false,
    "mqtt_broker": "<broker IP or hostname>",
    "mqtt_port": 1883,
    "mqtt_client_id": "<worker identifier>",
    "mqtt_topic": "<topic for this worker>",
    "mqtt_user": "<mqtt username, leave empty if not required>",
    "mqtt_password": "<mqtt password, leave empty if not required>",
    "ntp_host": "<NTP server>",
    "UNIX_EPOCH": false
}
```

See [`edge/README.md`](edge/README.md) for the meaning of each key and the installation steps.

---

## Fog Layer (`fog/`)

Runs on a secondary MicroPython node (TinyS3, ESP32-S3) installed on site.

Subscribes to one or more MQTT topics published by the edge devices on the edge-level broker and republishes every event, unchanged, on the cloud-level broker under `<mqtt_topic_cloud>/<operator topic>`. While the cloud broker is unreachable, events are kept in a queue and forwarded when the connection returns.

### Configuration (`config.json`)

```json
{
    "wifi_ssid": "<WiFi network name>",
    "wifi_pass": "<WiFi password>",
    "mqtt_broker": "<edge-level broker IP or hostname>",
    "mqtt_port": 1883,
    "mqtt_user": "<mqtt username, leave empty if not required>",
    "mqtt_password": "<mqtt password, leave empty if not required>",
    "mqtt_client_id": "<fog node identifier>",
    "mqtt_topic_operators": ["<topic of operator 1>", "<topic of operator 2>"],
    "cloud_mqtt_broker": "<cloud-level broker IP or hostname>",
    "cloud_mqtt_port": 1883,
    "cloud_mqtt_user": "<mqtt username, leave empty if not required>",
    "cloud_mqtt_password": "<mqtt password, leave empty if not required>",
    "mqtt_topic_cloud": "<topic of the workplace>"
}
```

See [`fog/README.md`](fog/README.md) for details.

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
- **IMU sensor** — WT9011DCL-BT50 (BLE; accelerometer, gyroscope and orientation angles are used, the magnetometer is not used)
- **Fog node** — ESP32-S3 TinyS3

Sensor placement: sacral region.

---

## MQTT Event Format

Events published by the edge device at the end of each near-miss event:

```json
{
    "eventType": "near_miss",
    "timestamp": 847550617,
    "sensorId": "workers_1",
    "eventStart": 847550612369,
    "eventEnd": 847550616369,
    "durationMs": 4000,
    "windows": 3
}
```

`timestamp` is the detection time in seconds; `eventStart` and `eventEnd` are in milliseconds; `windows` is the number of consecutive near-miss windows that form the event. By default times use the device epoch (2000-01-01 UTC on the ESP32); set `UNIX_EPOCH` to `true` in `config.json` for Unix times.
