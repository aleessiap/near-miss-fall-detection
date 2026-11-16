# Ring buffer of time-stamped multichannel samples.
#
# All channels share one timestamp ring, so a sample is stored once and every
# channel of a window is extracted with the same time boundaries. Values are
# kept in array('f') (single precision, like MicroPython floats on the ESP32),
# which uses far less RAM than lists of float objects and creates no garbage
# on append.

import time
from array import array


class SampleBuffer:
    """Fixed-capacity ring buffer of samples with one value per channel.

    Timestamps are ``time.ticks_ms()`` values (or any increasing integer
    milliseconds) and are compared with ``time.ticks_diff``, so the buffer keeps
    working when the millisecond counter wraps around.
    """

    def __init__(self, channels, capacity):
        self.channels = list(channels)
        self.capacity = capacity
        self._index = {name: i for i, name in enumerate(self.channels)}
        self._t = array('i', bytes(4 * capacity))
        self._v = [array('f', bytes(4 * capacity)) for _ in self.channels]
        self._next = 0      # position of the next write
        self._count = 0     # number of valid samples (<= capacity)
        self.overwritten_in_window = 0   # see window()

    def __len__(self):
        return self._count

    def clear(self):
        self._next = 0
        self._count = 0

    def append(self, t_ms, values):
        """Store one sample. ``values`` follows the order of ``channels``."""
        i = self._next
        self._t[i] = t_ms
        for c in range(len(self._v)):
            self._v[c][i] = values[c]
        self._next = (i + 1) % self.capacity
        if self._count < self.capacity:
            self._count += 1

    def newest_time(self):
        if self._count == 0:
            return None
        return self._t[(self._next - 1) % self.capacity]

    def oldest_time(self):
        if self._count == 0:
            return None
        return self._t[(self._next - self._count) % self.capacity]

    def window(self, t_end, length_ms, names):
        """Return the samples with ``t_end - length_ms <= t < t_end``.

        The interval is closed on the left and open on the right, the same
        convention used to cut the windows of the training set.

        Returns ``(timestamps, {name: values})`` with plain lists ordered from
        the oldest to the newest sample. Only the requested channels are copied.
        If the whole buffer lies inside the window the oldest samples may have
        been overwritten: this is counted in ``overwritten_in_window`` (the
        capacity must be large enough for this never to happen).
        """
        idx = []
        n = self._count
        cap = self.capacity
        # walk backwards from the newest sample: the window is at the end
        for k in range(1, n + 1):
            i = (self._next - k) % cap
            age = time.ticks_diff(t_end, self._t[i])
            if age <= 0:
                continue                    # at or after t_end: not in window
            if age > length_ms:
                break                       # older than the window start
            idx.append(i)
        else:
            if n == cap and idx:
                self.overwritten_in_window += 1
        idx.reverse()
        ts = [self._t[i] for i in idx]
        out = {}
        for name in names:
            col = self._v[self._index[name]]
            out[name] = [col[i] for i in idx]
        return ts, out
