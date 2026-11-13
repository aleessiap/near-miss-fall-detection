# Per-sample preprocessing: derived channels and buffering.
#
# Every decoded IMU sample goes through Preprocessor.add(), which computes the
# vector magnitudes required by the model (Euclidean norm, as in the training
# pipeline) and stores the sample in the shared SampleBuffer. Window
# statistics are NOT computed here: they are computed once per inference
# step on a frozen copy of the window (see machine_learning_inference.py).
# Standardisation (StandardScaler of the training set) is applied by
# lib/model_device.py.

import math
from lib.sample_buffer import SampleBuffer

# Order of the values in a decoded sample (see data_processor.py): the 9
# channels used by the system.
RAW_CHANNELS = ('AccX', 'AccY', 'AccZ',
                'GyroX', 'GyroY', 'GyroZ',
                'AngX', 'AngY', 'AngZ')

# Derived channels that the preprocessor knows how to compute.
DERIVED_CHANNELS = ('AccMag', 'GyroMag', 'AngMag')


def buffer_capacity(sampling_rate_hz, window_ms):
    """Ring buffer size: twice the expected samples of one window, plus a
    margin for bursts of samples arriving close together."""
    return int(math.ceil(sampling_rate_hz * window_ms / 1000.0 * 2)) + 8


class Preprocessor:
    """Computes the channels needed by the model and buffers each sample.

    ``channels`` is the list of channels the model needs (for example
    ``model_input_array.REQUIRED_DIMENSIONS``). An unknown channel raises an
    error at start-up instead of silently producing zero features.
    """

    def __init__(self, channels, capacity):
        unknown = [c for c in channels
                   if c not in RAW_CHANNELS and c not in DERIVED_CHANNELS]
        if unknown:
            raise ValueError('channels not computed by the preprocessor: %s' % unknown)
        self.channels = list(channels)
        self.buffer = SampleBuffer(self.channels, capacity)
        self._raw_pos = {name: i for i, name in enumerate(RAW_CHANNELS)}
        self._row = [0.0] * len(self.channels)

    def add(self, t_ms, sample):
        """Process one decoded sample (tuple ordered as RAW_CHANNELS)."""
        ax, ay, az, gx, gy, gz, nx, ny, nz = sample
        derived = {
            'AccMag': math.sqrt(ax * ax + ay * ay + az * az),
            'GyroMag': math.sqrt(gx * gx + gy * gy + gz * gz),
            'AngMag': math.sqrt(nx * nx + ny * ny + nz * nz),
        }
        row = self._row
        for i, name in enumerate(self.channels):
            pos = self._raw_pos.get(name)
            row[i] = sample[pos] if pos is not None else derived[name]
        self.buffer.append(t_ms, row)
