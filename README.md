# Near-Miss Fall Detection with Edge AI Wearables

This repository contains the dataset and embedded firmware associated with the paper:

> **“An Edge AI Wearable System for Near-Miss Fall Detection”**

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
├── firmware/                # Embedded software for the wearable device
│
└── README.md
```

---

## Folder Description

### `dataset/`

Contains the inertial dataset acquired during the experimental campaign.

- `raw/` contains the original IMU recordings collected from the wearable device.
- `features/` contains the processed dataset obtained through preprocessing, sliding-window segmentation, feature extraction, and annotation.

The processed dataset includes both Activities of Daily Living (ADLs) and near-miss fall samples:

- `1`  → ADLs
- `-1` → Near-miss falls

---

### `firmware/`

Contains the embedded software running on the wearable device, including sensor acquisition, preprocessing, on-device inference, and MQTT-based event communication.

---

## Hardware

- ESP32-S3 TinyS3
- WT9011DCL-BT50 IMU
- BLE + WiFi communication

Sensor placement: sacral region.
