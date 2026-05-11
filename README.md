# Near-Miss Fall Detection with Edge AI Wearables

This repository contains the dataset and embedded firmware associated with the paper:

> **"An Edge AI Wearable System for Near-Miss Fall Detection"**

The work presents a lightweight wearable framework for real-time near-miss fall detection using a single IMU and on-device machine learning inference.  
The proposed system combines wearable sensing, embedded AI, and event-driven communication to enable privacy-aware and low-power monitoring on resource-constrained devices.

The framework was evaluated on a dataset collected from 20 participants performing both Activities of Daily Living (ADLs) and controlled near-miss fall events under realistic outdoor conditions.

---

## Repository Structure

```text
.
├── dataset/
│   ├── raw/                 # Raw IMU recordings
│   └── features/            # Processed feature-based dataset
│
├── firmware/
│   ├── edge/                # MicroPython firmware for the ESP32-S3 wearable node
│   ├── fog/                 # MicroPython firmware for the fog relay node
│   └── test-mqtt-broker/    # Dockerized Mosquitto broker for local testing
│
└── README.md
```

---

## Folder Description

### `dataset/`

Contains the inertial dataset acquired during the experimental campaign.

`raw/` contains the original IMU recordings collected from the wearable device. `features/` contains the processed dataset obtained through preprocessing, sliding-window segmentation, feature extraction, and annotation.

The processed dataset includes both Activities of Daily Living (ADLs) and near-miss fall samples:

- `1`  → ADLs
- `-1` → Near-miss falls

---

### `firmware/`

Contains the embedded software stack for the full system, organized into three components.

The **edge node** runs a fully asynchronous MicroPython pipeline on the ESP32-S3 TinyS3: it acquires raw inertial data from the IMU over BLE, extracts 90 statistical features per sliding window (mean, std, variance, range, IQR, energy, SMA, skewness, kurtosis, pairwise correlations and covariances), and runs on-device inference with an embedded XGBoost model. On a near-miss detection, it publishes a JSON event to an MQTT broker.

The **fog node** runs on a secondary MicroPython device. It subscribes to the MQTT topics published by one or more edge devices and forwards detection events to a cloud REST API via HTTP POST.

The **test MQTT broker** is a Dockerized Eclipse Mosquitto instance for local development and testing.

See [`firmware/README.md`](firmware/README.md) for the full configuration reference and operating modes.

---

## Hardware

- ESP32-S3 TinyS3
- WT9011DCL-BT50 IMU (9-axis: accelerometer, gyroscope, magnetometer)
- BLE + WiFi communication

Sensor placement: sacral region.
