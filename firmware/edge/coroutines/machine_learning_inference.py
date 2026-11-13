# On-device inference and near-miss event detection.
#
# Every STEP_MS (1 s, i.e. 50% overlap with 2 s windows) the inference task:
#   1. takes the samples of the last WINDOW_MS from the buffer,
#      [t_end - WINDOW_MS, t_end), the same window definition used in training;
#   2. discards windows that cannot be processed reliably (fewer than
#      MIN_WINDOW_SAMPLES samples, or a non-finite feature), as the training
#      pipeline does;
#   3. computes the features in the order expected by the model
#      (lib/model_input_array.py) and runs the model (lib/model_device.py),
#      with its default decision rule (score > 0.5);
#   4. updates the EventTracker.
#
# Event rule (the same used in the event-level evaluation of the paper):
# consecutive windows classified as near-miss (window starts STEP_MS apart)
# are merged into one event, which spans from the start of the first window
# to the end of the last one. A single MQTT message is sent when the event
# ends, i.e. at the first window that is classified as normal activity or
# cannot be classified.
#
# To use another model, replace the three generated files in lib/
# (model_device.py, model_device.bin, model_input_array.py): nothing in this
# module depends on the number or the order of the features.

import gc
import json
import math
import time
import uasyncio as asyncio
import lib.model_device as model
import lib.model_input_array as features
from lib.window_features import WindowFeatures
import battery_test as bt
from lib.console import log
from lib.primitives.queue import QueueFull

EVENT_TYPE = 'near_miss'

# Message times use the epoch of time.time(): 2000-01-01 UTC on the ESP32
# port of MicroPython. With UNIX_EPOCH = true in config.json they are Unix
# times (1970-01-01 UTC), 3 bytes longer per message.
_DEVICE_TO_UNIX_S = 946684800 if time.gmtime(0)[0] == 2000 else 0
_offset_s = 0


def configure_time(cfg):
    """Select the epoch of the message times (call once at start-up)."""
    global _offset_s
    _offset_s = _DEVICE_TO_UNIX_S if cfg.get('UNIX_EPOCH', False) else 0


def epoch_ms(t_ticks):
    """Convert a ticks_ms timestamp to milliseconds of the device clock
    (synchronised by NTP when the Wi-Fi connects)."""
    now_ticks = time.ticks_ms()
    now_ms = time.time_ns() // 1_000_000 + _offset_s * 1000
    return now_ms - time.ticks_diff(now_ticks, t_ticks)


class EventTracker:
    """Merges consecutive positive windows into events.

    update() is called once per inference step with the window end time and
    the prediction; it returns a finished event (a dict) when an event ends,
    otherwise None.
    """

    def __init__(self, window_ms):
        self.window_ms = window_ms
        self.start = None       # ticks_ms start of the open event
        self.end = None         # ticks_ms end of the last positive window
        self.windows = 0

    def _close(self):
        event = {'start': self.start, 'end': self.end, 'windows': self.windows}
        self.start = self.end = None
        self.windows = 0
        return event

    def update(self, t_end, positive, contiguous=True):
        """``contiguous`` is False when one or more steps were skipped: the
        windows are no longer adjacent, so an open event is closed first."""
        finished = None
        if self.start is not None and not contiguous:
            finished = self._close()
        if positive:
            if self.start is None:
                self.start = time.ticks_add(t_end, -self.window_ms)
            self.end = t_end
            self.windows += 1
        elif self.start is not None:
            finished = self._close()
        return finished


# Queued messages keep their times as ticks_ms; payload() converts them to
# clock times when the message is published. Messages queued before the
# first NTP synchronisation (no Wi-Fi at start-up) therefore carry correct
# times as well.

def event_message(event, sensor_id, event_type=EVENT_TYPE):
    """Outgoing record of one event (see payload())."""
    return {'eventType': event_type, 'sensorId': sensor_id,
            'detected': time.ticks_ms(), 'start': event['start'],
            'end': event['end'], 'windows': event['windows']}


def window_message(t_end, window_ms, sensor_id, event_type):
    """Outgoing record of one near-miss window (battery test modes W and W1,
    where a message is sent for every window instead of every event)."""
    return {'eventType': event_type, 'sensorId': sensor_id,
            'detected': time.ticks_ms(),
            'start': time.ticks_add(t_end, -window_ms), 'end': t_end}


def payload(rec):
    """MQTT payload (JSON) of an outgoing record. Events: event type,
    detection time (s), device identifier, start and end of the event (ms),
    its duration and the number of windows that form it."""
    msg = {'eventType': rec['eventType'],
           'timestamp': epoch_ms(rec['detected']) // 1000,
           'sensorId': rec['sensorId']}
    if 'windows' in rec:
        msg['eventStart'] = epoch_ms(rec['start'])
        msg['eventEnd'] = epoch_ms(rec['end'])
        msg['durationMs'] = time.ticks_diff(rec['end'], rec['start'])
        msg['windows'] = rec['windows']
    else:
        msg['windowStart'] = epoch_ms(rec['start'])
        msg['windowEnd'] = epoch_ms(rec['end'])
    return json.dumps(msg)


def enqueue(queue, msg):
    """Put a message in the outgoing queue without waiting. If the queue is
    full (network down for a while) the message is dropped and counted
    (events_dropped): the inference must never stop because of the network."""
    try:
        queue.put_nowait(msg)
    except QueueFull:
        bt.count('events_dropped')
        log('inference: outgoing queue full, message dropped')


def load_model(model_path='lib/model_device.bin'):
    """Load the model tables and record memory use and size for the logs."""
    import os
    gc.collect()
    free_before = gc.mem_free()
    t = time.ticks_ms()
    model.load(model_path)
    load_ms = time.ticks_diff(time.ticks_ms(), t)
    gc.collect()
    bt.set_info('model', model.MODEL_NAME)
    bt.set_info('model_features', model.N_FEATURES)
    bt.set_info('model_file_bytes', os.stat(model_path)[6])
    bt.set_info('model_ram_bytes', free_before - gc.mem_free())
    bt.set_info('model_load_ms', load_ms)
    log('inference: model %s loaded (%d features, %d bytes of RAM, %d ms)' % (
        model.MODEL_NAME, model.N_FEATURES, free_before - gc.mem_free(), load_ms))


def check_model(buffer):
    """Stop with a clear error if the buffer lacks a channel the model needs
    (otherwise the features of that channel would silently be 0) or if the
    generated model files do not belong together."""
    missing = [c for c in features.REQUIRED_DIMENSIONS if c not in buffer.channels]
    if missing:
        raise ValueError('channels required by the model are not buffered: %s' % missing)
    if features.N_FEATURES != model.N_FEATURES:
        raise ValueError('model_input_array.py and model_device.py come from different models')


def _finite(x):
    for v in x:
        if not math.isfinite(v):
            return False
    return True


def predict_window(buffer, t_end, window_ms, min_samples=2):
    """Features and prediction of the window ending at t_end.

    Returns (prediction, score, n_samples, feature_us, predict_us, values).
    prediction is None when the window cannot be processed: fewer than
    ``min_samples`` samples (e.g. IMU disconnected) or a non-finite feature.
    The prediction is the decision rule of model.predict() (score >
    THRESHOLD), applied here so that the score is also available.
    """
    t0 = time.ticks_us()
    ts, values = buffer.window(t_end, window_ms, features.REQUIRED_DIMENSIONS)
    if len(ts) < min_samples:
        return None, None, len(ts), 0, 0, values
    x = WindowFeatures(ts, values).input_array(features.build_input_array)
    t1 = time.ticks_us()
    if not _finite(x):
        return None, None, len(ts), time.ticks_diff(t1, t0), 0, values
    s = model.score(x)
    pred = 1 if s > model.THRESHOLD else 0
    t2 = time.ticks_us()
    return pred, s, len(ts), time.ticks_diff(t1, t0), time.ticks_diff(t2, t1), values


def _range(v):
    return max(v) - min(v) if v else 0.0


def print_window(pred, s, n, values):
    """Debug line for one window: decision, score and how much the IMU moved
    (range of acceleration and angular velocity magnitudes in the window)."""
    log('window: %-9s score %.3f (threshold %.2f) | %d samples | AccMag range %.2f g | GyroMag range %.0f deg/s' % (
        'NEAR-MISS' if pred == 1 else 'normal', s, model.THRESHOLD, n,
        _range(values.get('AccMag')), _range(values.get('GyroMag'))))


async def inference_task(buffer, outgoing_queue, sensor_id, cfg):
    """Run one inference step every STEP_MS on the last WINDOW_MS of data.

    Detected events are put in ``outgoing_queue`` (one message per event)
    when MQTT event messages are enabled.
    """
    window_ms = int(cfg.get('WINDOW_MS', 2000))
    step_ms = int(cfg.get('STEP_MS', 1000))
    min_samples = max(2, int(cfg.get('MIN_WINDOW_SAMPLES', 2)))
    # one line per window on the serial console (normal operation only:
    # printing would add to the time and energy measured in battery tests)
    debug = bool(cfg.get('DEBUG_WINDOWS', False)) and not bt.ACTIVE
    check_model(buffer)
    tracker = EventTracker(window_ms)

    # wait until the buffer holds a complete window
    while True:
        oldest = buffer.oldest_time()
        if oldest is not None and time.ticks_diff(time.ticks_ms(), oldest) >= window_ms:
            break
        await asyncio.sleep_ms(100)
    log('inference: started (window %d ms, step %d ms)' % (window_ms, step_ms))

    t_next = time.ticks_ms()
    prev_end = None
    while True:
        wait = time.ticks_diff(t_next, time.ticks_ms())
        if wait > 0:
            await asyncio.sleep_ms(wait)
        t_end = t_next
        t_next = time.ticks_add(t_next, step_ms)
        # if the task is late by a whole step or more, skip the missed steps
        late = time.ticks_diff(time.ticks_ms(), t_next)
        if late >= 0:
            skipped = late // step_ms + 1
            t_next = time.ticks_add(t_next, skipped * step_ms)
            bt.count('skipped_steps', skipped)
        # adjacent windows start exactly one step apart
        contiguous = prev_end is not None and time.ticks_diff(t_end, prev_end) == step_ms
        prev_end = t_end

        pred, s, n, feat_us, pred_us, values = predict_window(buffer, t_end, window_ms, min_samples)
        if pred is None:                  # window discarded: it ends any open event
            bt.count('discarded_windows')
            event = tracker.update(t_end, False, contiguous=False)
            if debug:
                log('window: discarded (%d samples)' % n)
        else:
            bt.count('inferences')
            bt.record_timing(feat_us, pred_us)
            event = tracker.update(t_end, pred == 1, contiguous)
            if pred == 1:
                bt.count('detected_windows')
            if debug:
                print_window(pred, s, n, values)
        if event is not None:
            bt.count('detections')
            log('inference: near-miss event, %d ms, %d windows' % (
                time.ticks_diff(event['end'], event['start']), event['windows']))
            # battery tests: detections are counted but not sent, so that the
            # message traffic is the controlled simulated one
            if bt.SEND_REAL_EVENTS:
                enqueue(outgoing_queue, event_message(event, sensor_id))
