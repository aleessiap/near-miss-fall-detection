# Battery discharge test support.
#
# Set MODE below and copy this file to the device. With MODE = None the
# firmware runs normally and this module does nothing.
#
# Modes (same firmware, parts switched on or off):
#   "A"    BLE acquisition and buffering only, Wi-Fi off. Baseline consumption.
#   "B"    acquisition + feature extraction and inference, Wi-Fi off.
#          B - A is the cost of on-device inference.
#   "C"    acquisition + inference + Wi-Fi/MQTT, one message per event (the
#          complete system). Message traffic is controlled: one simulated
#          event every SIMULATED_EVENT_PERIOD_S, with SIMULATED_WINDOWS
#          windows per event used in turn (rate and length observed in the
#          protocol: about 60 events per hour, 2.43 windows per event).
#          Detections on the device lying still are counted in the log
#          (detections, detected_windows) but not sent.
#   "W"    as C, but one message per near-miss window instead of one per
#          event. C vs W is the effect of merging adjacent windows.
#   "W1"   as W with a near-miss in every window: one message per second
#          (upper bound of per-window messaging, gives the energy per
#          message).
#   "IMU"  as A, with the board powered from USB: measures the autonomy of
#          the IMU's own battery.
# In every mode raw IMU data never leave the device: only event messages
# (or, in W and W1, window messages) are sent over MQTT.
#
# The full system at 100 Hz is mode C with ACQUISITION_MODE = "100Hz".
#
# How a test runs:
#   - Modes A, B, C, W, W1: the test starts in one of two ways (t = 0, a new log file
#     is created):
#       * power-on from the battery (e.g. with a battery switch): if the board
#         starts without USB power and the battery is at least
#         START_MIN_VOLTAGE, the test starts at boot (t = 0 is the boot time);
#       * USB unplugged: if the board started on USB (battery charging), the
#         test starts when USB power is removed.
#     The test ends when the battery is exhausted: the last line written gives
#     the end time. Reconnecting USB during a test ends it
#     ("END USB_RECONNECTED", test not valid). The voltage threshold avoids
#     starting a new test when an exhausted battery briefly restarts the board.
#     In these modes the board connects to the IMU only while a test is
#     running: a board that is charging, or whose test has ended, never takes
#     the IMU (which accepts a single connection) away from the board under
#     test. Several boards can therefore share one IMU, one test at a time.
#   - Mode IMU: the test starts when the IMU connects and ends when no IMU
#     data has been received for IMU_LOST_TIMEOUT_S ("END IMU_LOST").
#   - While a test runs the LED gives one short green blink at every log
#     line: no blinks means that the test is over (or the board is off).
#   - Every LOG_PERIOD_S a line is appended to logs/<MODE>_<board>_<n>.csv,
#     where <board> is the last 6 digits of the board id. The file
#     is opened, written and closed each time, so it survives the power cut.

import gc
import os
import time
import machine
from lib.console import log

# ─── Settings ────────────────────────────────────────────────────────────────
MODE = None                     # None | "A" | "B" | "C" | "W" | "W1" | "IMU"
LED_ENABLED = False             # LED off during tests, in every mode
LOG_PERIOD_S = 60               # one log line per minute
SIMULATED_EVENT_PERIOD_S = 60   # modes C, W: one simulated event per minute
SIMULATED_WINDOWS = (2, 3)      # modes C, W: windows per simulated event, used in turn
IMU_LOST_TIMEOUT_S = 600        # mode IMU: end of test without IMU data
START_MIN_VOLTAGE = 4.0         # power-on start: minimum battery voltage (V)
LOG_DIR = 'logs'
# ─────────────────────────────────────────────────────────────────────────────

_VALID = (None, 'A', 'B', 'C', 'W', 'W1', 'IMU')
if MODE not in _VALID:
    raise ValueError('battery_test.MODE must be one of %s' % (_VALID,))

ACTIVE = MODE is not None
# What runs in each mode. Normal operation (MODE = None) = complete system.
WIFI = MODE in (None, 'C', 'W', 'W1')
PREPROCESS = MODE in (None, 'A', 'B', 'C', 'W', 'W1', 'IMU')
INFERENCE = MODE in (None, 'B', 'C', 'W', 'W1')
SEND_REAL_EVENTS = MODE is None          # tests: detections counted, not sent
SIMULATED_EVENTS = MODE in ('C', 'W', 'W1')
PER_WINDOW_MESSAGES = MODE in ('W', 'W1')
CONTINUOUS_NEAR_MISS = MODE == 'W1'
LED_ON = LED_ENABLED or not ACTIVE

COUNTERS = ('samples', 'inferences', 'events', 'sim_events',
            'mqtt_bytes', 'mqtt_errors', 'mqtt_reconnects',
            'imu_disconnects', 'skipped_steps', 'queue_max', 'queue_dropped',
            'events_dropped', 'wifi_retries', 'detections', 'detected_windows',
            'discarded_windows')
COLUMNS = (('t_s', 'vbat', 'vbus', 'mem_free', 'last_sample_s') + COUNTERS +
           ('feat_us_mean', 'feat_us_max', 'pred_us_mean', 'pred_us_max'))

_counts = {k: 0 for k in COUNTERS}
_info = {}                  # key=value pairs written in the log header
_timing = [0, 0, 0, 0, 0]   # n, feat_sum, feat_max, pred_sum, pred_max
_state = {'file': None, 't0': None, 'last_sample': None, 'finished': False}


# ─── Hooks called by the firmware (all cheap no-ops when MODE is None) ───────
def count(name, n=1):
    if ACTIVE:
        _counts[name] += n


def set_max(name, value):
    """Keep the maximum of a counter (e.g. queue length)."""
    if ACTIVE and value > _counts[name]:
        _counts[name] = value


def on_imu_packet():
    """Called for every decoded IMU sample."""
    if ACTIVE:
        _counts['samples'] += 1
        _state['last_sample'] = time.ticks_ms()


def on_imu_connected():
    if MODE == 'IMU' and _state['file'] is None:
        start('imu_connected')
    note('IMU_CONNECTED')


def on_imu_disconnected():
    count('imu_disconnects')
    note('IMU_DISCONNECTED')


def record_timing(feat_us, pred_us):
    """Feature extraction and prediction time of one window, in us."""
    if ACTIVE:
        t = _timing
        t[0] += 1
        t[1] += feat_us
        t[3] += pred_us
        if feat_us > t[2]:
            t[2] = feat_us
        if pred_us > t[4]:
            t[4] = pred_us


def set_info(key, value):
    """Store a value for the log header (model size, RAM, message sizes...)."""
    _info[key] = value


def running():
    return _state['file'] is not None and not _state['finished']


def imu_allowed():
    """Whether the firmware may connect to the IMU now.

    Normal operation and mode IMU: always. Other modes: only while a test is
    running, so that a board on USB (charging) or a board whose test has ended
    does not occupy the IMU.
    """
    if MODE in (None, 'IMU'):
        return True
    return running()


# ─── Battery and USB ─────────────────────────────────────────────────────────
def battery_voltage():
    try:
        import tinys3
        return tinys3.get_battery_voltage()
    except Exception:
        return -1.0


def usb_present():
    try:
        import tinys3
        return tinys3.get_vbus_present()
    except Exception:
        return False


# ─── Log file ────────────────────────────────────────────────────────────────
def _elapsed_s():
    return time.ticks_diff(time.ticks_ms(), _state['t0']) / 1000.0


def _append(text):
    f = open(_state['file'], 'a')
    f.write(text)
    f.close()


def device_id():
    """Unique identifier of the board, read from the chip (hex string).
    Tests run on different boards can be told apart without any setting."""
    import ubinascii
    return ubinascii.hexlify(machine.unique_id()).decode()


def _new_log_name():
    """logs/<MODE>_<last 6 digits of the board id>_<n>.csv: logs copied from
    several boards into the same folder never overwrite each other."""
    try:
        os.mkdir(LOG_DIR)
    except OSError:
        pass                                  # already exists
    existing = os.listdir(LOG_DIR)
    dev = device_id()[-6:]
    i = 1
    while '%s_%s_%d.csv' % (MODE, dev, i) in existing:
        i += 1
    return '%s/%s_%s_%d.csv' % (LOG_DIR, MODE, dev, i)


def start(trigger, t0=None):
    """Start the test: create the log file and write its header.

    ``trigger`` describes what started the test (written in the header);
    ``t0`` is the ticks_ms time zero of the test (default: now; 0 = boot).
    """
    if not ACTIVE or _state['file'] is not None:
        return
    _state['t0'] = time.ticks_ms() if t0 is None else t0
    _state['file'] = _new_log_name()
    for k in COUNTERS:                        # count from the start of the test
        _counts[k] = 0
    _timing[:] = [0, 0, 0, 0, 0]
    gc.collect()
    header = {
        'mode': MODE,
        'device_id': device_id(),
        'start_trigger': trigger,
        'reset_cause': machine.reset_cause(),
        'cpu_freq_hz': machine.freq(),
        'vbat_start': battery_voltage(),
        'usb_at_start': int(usb_present()),
        'log_period_s': LOG_PERIOD_S,
        'simulated_event_period_s': (1 if CONTINUOUS_NEAR_MISS else SIMULATED_EVENT_PERIOD_S)
                                    if SIMULATED_EVENTS else 0,
        'simulated_windows': '/'.join(str(n) for n in SIMULATED_WINDOWS) if SIMULATED_EVENTS else '',
        'message_per': ('window' if PER_WINDOW_MESSAGES else 'event') if SIMULATED_EVENTS else '',
        'real_events_sent': int(SEND_REAL_EVENTS),
        'led_enabled': int(LED_ON),
        'mem_free_start': gc.mem_free(),
    }
    header.update(_info)
    lines = ''.join('# %s=%s\n' % (k, v) for k, v in header.items())
    _append(lines + ','.join(COLUMNS) + '\n')
    log('battery_test: test started, logging to', _state['file'])


def note(text):
    """Write a comment line with the current test time (e.g. disconnections)."""
    if running():
        _append('# t_s=%.1f %s\n' % (_elapsed_s(), text))


def finish(reason):
    """End the test with a final line; nothing is logged afterwards."""
    if running():
        _write_line()
        _append('# END t_s=%.1f reason=%s\n' % (_elapsed_s(), reason))
        _state['finished'] = True
        log('battery_test: test finished,', reason)


def _write_line():
    t = _timing
    n = t[0]
    last = _state['last_sample']
    last_s = (time.ticks_diff(last, _state['t0']) / 1000.0) if last is not None else -1
    gc.collect()
    row = [round(_elapsed_s(), 1), battery_voltage(), int(usb_present()),
           gc.mem_free(), round(last_s, 1)]
    row += [_counts[k] for k in COUNTERS]
    row += [t[1] // n if n else 0, t[2], t[3] // n if n else 0, t[4]]
    _append(','.join(str(v) for v in row) + '\n')
    _timing[:] = [0, 0, 0, 0, 0]              # timing is per log period


# ─── Tasks ───────────────────────────────────────────────────────────────────
async def supervisor_task(heartbeat=None):
    """Starts and ends the test and writes one log line every LOG_PERIOD_S.

    ``heartbeat`` (optional) is called after every log line, e.g. to blink
    the LED so that a running test can be recognised.
    """
    import uasyncio as asyncio
    if not ACTIVE:
        return
    log('battery_test: mode', MODE)
    usb_before = usb_present()
    if MODE != 'IMU':
        if usb_before:
            log('battery_test: charge the battery, then unplug USB to start the test '
                  '(the IMU is connected only when the test starts)')
        else:
            # powered on from the battery: the test starts now, with t = 0 at boot
            v = battery_voltage()
            if v >= START_MIN_VOLTAGE:
                start('power_on', t0=0)
            else:
                log('battery_test: started from a battery at %.2f V (< %.2f V): test not started'
                      % (v, START_MIN_VOLTAGE))
    next_log = None
    waited_s = 0
    while not _state['finished']:
        await asyncio.sleep_ms(1000)
        usb = usb_present()
        if MODE != 'IMU':
            if _state['file'] is None:
                waited_s += 1
                if waited_s % 30 == 0:        # while charging: show the voltage
                    log('battery_test: waiting, USB %s, battery %.2f V' % (
                        'on' if usb else 'off', battery_voltage()))
                if usb_before and not usb:
                    start('usb_unplugged')    # USB removed: t = 0
            elif usb:
                finish('USB_RECONNECTED')
                break
        usb_before = usb
        if not running():
            continue
        if next_log is None:
            next_log = time.ticks_add(_state['t0'], LOG_PERIOD_S * 1000)
        if time.ticks_diff(time.ticks_ms(), next_log) >= 0:
            _write_line()
            if heartbeat is not None:
                heartbeat()
            # next period; skip periods already past (e.g. a slow start-up)
            while time.ticks_diff(time.ticks_ms(), next_log) >= 0:
                next_log = time.ticks_add(next_log, LOG_PERIOD_S * 1000)
        if MODE == 'IMU':
            last = _state['last_sample']
            if last is not None and time.ticks_diff(time.ticks_ms(), last) > IMU_LOST_TIMEOUT_S * 1000:
                finish('IMU_LOST')
