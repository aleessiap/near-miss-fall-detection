# Dataset

## Table of Contents

- [Overview](#overview)
- [Folder Structure](#folder-structure)
- [Main Dataset](#main-dataset-main_35hz)
- [External Test Group](#external-test-group-external_100hz)
- [File Format](#file-format)
- [Experimental Protocol](#experimental-protocol)
- [Annotation](#annotation)
- [Privacy](#privacy)
- [Hardware](#hardware)
- [Citation](#citation)

---

## Overview

This folder contains the inertial dataset collected during the experimental campaign for near-miss fall detection, released with the paper *An Edge AI Wearable System for Near-Miss Fall Detection*.

The data were acquired using a wearable IMU positioned at the sacral region while participants performed both normal Activities of Daily Living (ADLs) and controlled near-miss fall events under realistic outdoor conditions. Participants walked an outdoor circuit with natural terrain variations and stairs, and simulated losses of balance at moments they chose within the designated phases of the protocol.

| Folder | Participants | Sampling | Recorded time | Near-miss falls |
| --- | --- | --- | --- | --- |
| `main_3.5Hz/` | 20 (`S01`-`S20`) | 3.5 Hz | 4.44 h | 251 |
| `external_100Hz/` | 7 (`E01`-`E07`) | 100 Hz | 1.73 h | 79 |

---

## Folder Structure

```text
dataset/
├── main_3.5Hz/              # Main dataset: one CSV file per participant (S01-S20)
├── external_100Hz/          # External test group: one CSV file per participant (E01-E07)
├── summary.csv              # Per-recording summary
└── SHA256SUMS.txt           # Checksums of all CSV files
```

`summary.csv` lists, for each recording, the number of samples, the duration, the mean sampling interval, the number of near-miss samples and the number of near-miss falls.

---

## Main Dataset (`main_3.5Hz/`)

Contains the recordings of the 20 participants used to develop and evaluate the system (nested cross-validation), sampled at 3.5 Hz. Average session duration: 13.3 min (7.7 to 17.1 min).

---

## External Test Group (`external_100Hz/`)

Contains the recordings of 7 additional participants, acquired with the same protocol at the same site and sampled at 100 Hz. This group was used as an external test set and for the sampling-rate analysis.

---

## File Format

The recordings are stored in CSV format, one file per participant and one row per sample, and preserve the original temporal acquisition sequence. Values are in physical units, without filtering.

| Column | Unit | Description |
| --- | --- | --- |
| `Timestamp` | ms | Time from the start of the recording session (device clock) |
| `AccX`, `AccY`, `AccZ` | g | Linear acceleration |
| `GyroX`, `GyroY`, `GyroZ` | deg/s | Angular velocity |
| `AngX`, `AngY`, `AngZ` | deg | Orientation (Euler angles) |
| `Tag` | | Class label |

Each sample is associated with a class label:

- `1`  → ADLs
- `-1` → Near-miss fall event

An annotated near-miss fall is a continuous sequence of samples with `Tag = -1`. The magnetometer channels are not included.

---

## Experimental Protocol

Each session consisted of 11 phases:

- Sitting
- Straight walking
- Walking with lateral imbalances
- Recovery walk
- Walking with forward/backward imbalances
- Recovery walk
- Stair ascent
- Straight walking
- Stair descent
- Final walk
- Final sitting

Participants simulated 3-4 near-miss falls in each of the four instability phases.

---

## Annotation

Each session was video-recorded from behind. Five annotators, not involved in the study, annotated all sessions independently with written guidelines: a near-miss fall starts at the first video frame in which a loss of balance is visible and ends when the participant has recovered a stable posture.

The final label of each sample is the majority vote of the five annotators. Agreement (Fleiss' kappa on a common time grid of about 286 ms): 0.85 for the main dataset and 0.82 for the external group.

Video and sensor data were aligned on the moment in which the participant stands up at the start of the session. The videos were deleted after annotation.

---

## Privacy

Participants were informed about the public release of the pseudonymized IMU recordings and event annotations and gave their consent. Codes are not linked to any personal information, and no demographic data are included.

---

## Hardware

- ESP32-S3 TinyS3
- WT9011DCL-BT50 IMU (WitMotion), connected over BLE

Sensor placement: posterior side of the belt, approximately at the sacral region.

---

## Citation

If you use this dataset, please cite the paper *An Edge AI Wearable System for Near-Miss Fall Detection*.
