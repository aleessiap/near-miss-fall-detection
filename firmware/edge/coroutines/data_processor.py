# IMU acquisition (WitMotion WT9011DCL over BLE).
#
# Two acquisition modes, selected with ACQUISITION_MODE in config.json. Both
# deliver decoded samples to the same callback, on_sample(t_ms, sample),
# where t_ms is a time.ticks_ms() timestamp and sample is a tuple ordered as
# preprocessor.RAW_CHANNELS (9 channels):
#   (AccX, AccY, AccZ [g], GyroX, GyroY, GyroZ [deg/s], AngX, AngY, AngZ [deg])
# The magnetometer is not a model input and is not part of the sample.
# Everything downstream (buffering, windows, inference, events) is the same
# for both modes.
#
# "3.5Hz"  Request/response loop of the dataset recordings: wait for a sensor
#          packet, request the magnetometer registers, wait for the reply,
#          pause. The magnetometer request/reply is kept only because it is
#          part of the loop timing; its values are discarded. Each iteration
#          lasts at least SAMPLE_PERIOD_MS (default 284 ms, the mean sampling
#          interval of the dataset), so that the deployed model receives the
#          same sampling rate it was trained on. SAMPLE_PERIOD_MS = 0 disables
#          the pacing (free-running loop, about 5-7 samples/s).
#
# "100Hz"  Continuous output: the sensor is set to 100 Hz and pushes its
#          periodic packets (0x55 0x61) by itself. Every notification is
#          time-stamped on arrival in a deep queue (aioble keeps only the last
#          notification by default) and split into its 20-byte frames.
#          No 100 Hz model is deployed: this mode is used for measurements.

import struct
import time
from collections import deque
import uasyncio as asyncio
import battery_test as bt

# Sensor commands (WT9011DCL protocol)
MAG_REQUEST = bytes([0xFF, 0xAA, 0x27, 0x3A, 0x00])     # read registers from 0x3A (HX, HY, HZ, ...)
RATE_100HZ = bytes([0xFF, 0xAA, 0x03, 0x09, 0x00])      # output rate 100 Hz (not saved)

_ACC = 16 / 32768       # +-16 g
_GYRO = 2000 / 32768    # +-2000 deg/s
_ANG = 180 / 32768      # +-180 deg

_MIN_PAUSE_MS = 100     # pause of the dataset recording loop


def _get_signed_int(data):
    return struct.unpack("<h", bytes(data))[0]


# ─── "3.5Hz" ─────────────────────────────────────────────────────────────────
async def _decode_imu_data(imu_char_read, results):
    data = await imu_char_read.notified()
    if len(data) == 20:
        results[0] = _get_signed_int(data[2:4]) / 32768 * 16
        results[1] = _get_signed_int(data[4:6]) / 32768 * 16
        results[2] = _get_signed_int(data[6:8]) / 32768 * 16
        results[3] = _get_signed_int(data[8:10]) / 32768 * 2000
        results[4] = _get_signed_int(data[10:12]) / 32768 * 2000
        results[5] = _get_signed_int(data[12:14]) / 32768 * 2000
        results[6] = _get_signed_int(data[14:16]) / 32768 * 180
        results[7] = _get_signed_int(data[16:18]) / 32768 * 180
        results[8] = _get_signed_int(data[18:20]) / 32768 * 180


async def acquire_3p5hz(imu_char_read, imu_char_write, on_sample, period_ms=0):
    """Request/response acquisition loop of the dataset recordings.

    The timestamp is taken at the start of each iteration and the last
    decoded values are kept between iterations, as in the recording loop.
    ``period_ms`` is the minimum duration of one iteration (0 = no pacing).
    """
    results = [0.0] * 9
    while True:
        t_ms = time.ticks_ms()
        await _decode_imu_data(imu_char_read, results)
        await imu_char_write.write(MAG_REQUEST)
        await imu_char_read.notified()          # magnetometer reply: timing only
        on_sample(t_ms, tuple(results))
        rest = period_ms - time.ticks_diff(time.ticks_ms(), t_ms)
        await asyncio.sleep_ms(rest if rest > _MIN_PAUSE_MS else _MIN_PAUSE_MS)


# ─── "100Hz" ─────────────────────────────────────────────────────────────────
class TimedQueue:
    """Replacement for the notification queue of an aioble characteristic.

    aioble keeps only the most recent notification, so at 100 Hz most packets
    would be lost. This queue keeps up to ``size`` notifications together
    with their arrival time, taken in the BLE callback.
    """

    def __init__(self, size):
        self.q = deque((), size)
        self.size = size
        self.dropped = 0

    def append(self, data):
        if len(self.q) == self.size:
            self.dropped += 1           # deque full: the oldest item is lost
        self.q.append((time.ticks_ms(), data))

    def popleft(self):
        return self.q.popleft()

    def __len__(self):
        return len(self.q)


async def acquire_100hz(imu_char_read, imu_char_write, on_sample, cfg):
    """Continuous acquisition at the sensor output rate (100 Hz).

    Sample timestamps: a notification carries 4-5 frames that arrive together,
    so arrival times cannot be used directly. The sensor samples at a constant
    period, so frame k is stamped t0 + k * SENSOR_PERIOD_MS (board
    milliseconds). t0 tracks the lower envelope of the arrival times: it is
    moved back whenever a frame arrives earlier than its stamp, and drifts
    forward by SENSOR_CLOCK_RELAX_MS per frame so that a small error in the
    period cannot accumulate.

    All time arithmetic is done on integers (microseconds): MicroPython
    floats are single precision on the ESP32 and cannot hold millisecond
    tick values with enough resolution after a few hours.
    """
    period_us = int(round(float(cfg.get('SENSOR_PERIOD_MS', 10.0716)) * 1000))
    relax_us = int(round(float(cfg.get('SENSOR_CLOCK_RELAX_MS', 0.02)) * 1000))

    queue = TimedQueue(500)
    imu_char_read._notify_queue = queue
    await imu_char_read.subscribe(notify=True)
    await imu_char_write.write(RATE_100HZ)

    t0 = None               # ticks_ms origin of the frame clock
    counter = 0             # frames since t0
    offset_us = 0           # corrections of the origin, in us
    while True:
        bt.set_max('queue_max', len(queue))
        while len(queue):
            t_arrival, data = queue.popleft()
            n = len(data) - len(data) % 20
            for i in range(0, n, 20):
                if data[i] != 0x55 or data[i + 1] != 0x61:   # acc, gyro, angles only
                    continue
                v = struct.unpack_from('<9h', data, i + 2)
                if t0 is None:
                    t0 = t_arrival
                t_frame = time.ticks_add(t0, (counter * period_us + offset_us) // 1000)
                late = time.ticks_diff(t_frame, t_arrival)
                if late > 0:                          # stamp after arrival: move back
                    offset_us -= late * 1000
                    t_frame = time.ticks_add(t_frame, -late)
                offset_us += relax_us
                counter += 1
                if counter >= 1000:                   # rebase: keep integers small
                    shift_ms = (counter * period_us + offset_us) // 1000
                    t0 = time.ticks_add(t0, shift_ms)
                    offset_us = counter * period_us + offset_us - shift_ms * 1000
                    counter = 0
                on_sample(t_frame, (
                    v[0] * _ACC, v[1] * _ACC, v[2] * _ACC,
                    v[3] * _GYRO, v[4] * _GYRO, v[5] * _GYRO,
                    v[6] * _ANG, v[7] * _ANG, v[8] * _ANG))
        bt.set_max('queue_dropped', queue.dropped)
        await asyncio.sleep_ms(20)
