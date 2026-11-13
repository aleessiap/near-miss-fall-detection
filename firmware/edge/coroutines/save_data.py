# Data recording mode (register_data_mode = true in config.json).
#
# Every decoded sample is appended to imu_data_<n>.json, in the format of the
# recordings used to build the dataset: "[" followed by one JSON object per
# line, each followed by ",". The file is left without the closing bracket
# so that it stays valid to read even if power is lost. Samples are stored
# locally only, for experimental validation and offline analysis: they are
# never transmitted.

import json
import os
import time
from coroutines.preprocessor import RAW_CHANNELS


def get_unique_filename(base_name='imu_data'):
    """First imu_data_<n>.json that does not exist yet."""
    existing = os.listdir()
    i = 1
    while '%s_%d.json' % (base_name, i) in existing:
        i += 1
    return '%s_%d.json' % (base_name, i)


class DataRecorder:
    """Acquisition callback that appends each sample to a JSON file."""

    def __init__(self, filename):
        self.filename = filename
        self.t_first = None
        self.count = 0

    def add(self, t_ms, sample):
        if self.t_first is None:
            self.t_first = t_ms
        rec = {'Timestamp': time.ticks_diff(t_ms, self.t_first)}
        for name, v in zip(RAW_CHANNELS, sample):
            rec[name] = v
        with open(self.filename, 'a') as f:
            if self.count == 0:
                f.write('[')
            json.dump(rec, f)
            f.write(',\n')
        self.count += 1
