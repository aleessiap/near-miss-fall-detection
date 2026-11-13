# Near-Miss Fall Detection with Edge AI Wearables

<p align="center">
  <img src="https://img.shields.io/badge/MicroPython-2B2728?style=for-the-badge&logo=micropython&logoColor=white" alt="MicroPython">
  <img src="https://img.shields.io/badge/XGBoost-337AB7?style=for-the-badge&logo=xgboost&logoColor=white" alt="XGBoost">
  <img src="https://img.shields.io/badge/MQTT-660066?style=for-the-badge&logo=mqtt&logoColor=white" alt="MQTT">
  <img src="https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
</p>

---

## Table of Contents

- [About](#about)
- [Repository Structure](#repository-structure)
- [Folder Description](#folder-description)
- [Hardware](#hardware)
- [Software](#software)

---

## About

This repository contains the dataset and embedded firmware associated with the paper:

> **"An Edge AI Wearable System for Near-Miss Fall Detection"**

The work presents a lightweight wearable framework for real-time near-miss fall detection using a single IMU and on-device machine learning inference.  
The proposed system combines wearable sensing, embedded AI, and event-driven communication to enable privacy-aware and low-power monitoring on resource-constrained devices.

The framework was evaluated on a dataset collected from 20 participants performing both Activities of Daily Living (ADLs) and controlled near-miss fall events under realistic outdoor conditions, and tested on an external group of 7 participants recorded with the same protocol.


## Repository Structure

```text
.
├── dataset/
│   ├── main_3.5Hz/          # Main dataset: 20 participants, 3.5 Hz
│   ├── external_100Hz/      # External test group: 7 participants, 100 Hz
│   ├── summary.csv          # Per-recording summary
│   ├── SHA256SUMS.txt       # Checksums of the CSV files
│   └── README.md
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

`main_3.5Hz/` contains the recordings of the 20 participants used to develop and evaluate the system. `external_100Hz/` contains the recordings of the external group, used as an external test set and for the sampling-rate analysis. Each CSV file holds the IMU samples of one participant (acceleration, angular velocity, Euler angles) with a label per sample, obtained from the majority vote of five annotators:

- `1`  → ADLs
- `-1` → Near-miss falls

See [`dataset/README.md`](dataset/README.md) for the file format, the acquisition protocol and the annotation procedure.

---

### `firmware/`

Contains the embedded software stack for the full system, organized into three components.

The **edge node** runs a fully asynchronous MicroPython pipeline on the ESP32-S3 TinyS3: it acquires inertial data from the IMU over BLE, computes statistical features on sliding windows of 2 s (mean, median, std, variance, min, max, range, percentiles, IQR, energy, SMA, skewness, kurtosis, derivative, pairwise correlations and covariances), and runs on-device inference with an embedded XGBoost model using 53 selected features. At the end of each near-miss event, it publishes a JSON event to an MQTT broker. Raw IMU data never leave the device.

The **fog node** runs on a secondary MicroPython device installed on site. It subscribes to the MQTT topics published by one or more edge devices and forwards the events, unchanged, to a cloud-level MQTT broker.

The **test MQTT broker** is a Dockerized Eclipse Mosquitto instance for local development and testing.

See [`firmware/README.md`](firmware/README.md), [`firmware/edge/README.md`](firmware/edge/README.md) and [`firmware/fog/README.md`](firmware/fog/README.md) for the full configuration reference and operating modes.

---

## Hardware

- ESP32-S3 TinyS3
- WT9011DCL-BT50 IMU (accelerometer, gyroscope and orientation angles are used; the magnetometer is not used)
- BLE + WiFi communication

Sensor placement: sacral region.

---

## Software

| Component | Notes |
| --- | --- |
| MicroPython (ESP32-S3 / TinyS3) | Firmware of the edge and fog nodes |
| `umqtt.simple` (micropython-lib) | MQTT client of the edge and fog nodes |
| `aioble` (micropython-lib) | Async BLE library, included in `firmware/edge/lib/aioble/` |
| `primitives/queue.py` (micropython-async, Peter Hinch) | Async queue, included in `firmware/edge/lib/primitives/` |
| `tinys3.py` (Unexpected Maker) | TinyS3 helper library, included in `firmware/edge/` |
| Thonny | Used to upload the firmware to the boards |
| Eclipse Mosquitto (Docker) | Test MQTT broker (`firmware/test-mqtt-broker/`) |
