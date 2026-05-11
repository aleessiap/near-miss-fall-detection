# Dataset

## Table of Contents

- [Overview](#overview)
- [Folder Structure](#folder-structure)
- [Raw Recordings](#raw)
- [Processed Features](#features)
- [Experimental Protocol](#experimental-protocol)
- [Hardware](#hardware)

---

# Overview 

This folder contains the inertial dataset collected during the experimental campaign for near-miss fall detection.

The data were acquired using a wearable IMU positioned at the sacral region while participants performed both normal Activities of Daily Living (ADLs) and controlled near-miss fall events under realistic outdoor conditions.

---

## Folder Structure

```text
dataset/
├── raw/                     # Raw IMU recordings
└── features/                # Processed feature-based dataset
```

---

## `raw/`

Contains the original IMU recordings acquired directly from the wearable device during the experimental sessions.

Each recording contains timestamped measurements from:

- Accelerometer
- Gyroscope
- Magnetometer
- Orientation angles

The raw recordings are stored in CSV format and preserve the original temporal acquisition sequence.

Example channels include:

- `AccX`, `AccY`, `AccZ`
- `GyroX`, `GyroY`, `GyroZ`
- `AngX`, `AngY`, `AngZ`
- `MagX`, `MagY`, `MagZ`
- `Timestamp`

The raw dataset also includes the corresponding class labels:

- `1`  → ADLs
- `-1` → Near-miss fall events

---

## `features/`

Contains the processed dataset obtained after:

1. Signal preprocessing
2. Sliding-window segmentation
3. Feature extraction
4. Manual annotation of near-miss fall events

Each row corresponds to a temporal window represented through statistical and motion-related features extracted from the inertial signals.

Example extracted features include:

- Mean
- Standard deviation
- Variance
- Range
- Interquartile range (IQR)
- Energy
- Signal Magnitude Area (SMA)
- Skewness
- Kurtosis
- Correlation and covariance features

Each sample is associated with a class label:

- `1`  → ADLs
- `-1` → Near-miss fall event

The feature-based dataset is intended for machine learning training and evaluation.

---

## Experimental Protocol

The dataset was collected from 20 participants performing:

- Sitting
- Walking
- Stair ascent/descent
- Recovery walking
- Controlled lateral perturbations
- Controlled forward/backward perturbations

Near-miss fall events were manually annotated using synchronized video recordings during post-processing.

---

## Hardware

- ESP32-S3 TinyS3
- WT9011DCL-BT50 IMU

Sensor placement: sacral region.
