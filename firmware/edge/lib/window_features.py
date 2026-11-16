# Statistical features of one time window, computed exactly as in the
# training pipeline (pandas / NumPy / SciPy definitions):
#
#   mean, median           arithmetic mean, median (mean of the two middle values)
#   std, var               sample statistics (ddof = 1)
#   max, min, range        range = max - min
#   p90, iqr               percentiles with linear interpolation (NumPy default)
#   energy                 mean of the squared values
#   sma                    mean of the absolute values
#   skew, kurt             bias-corrected sample skewness and excess kurtosis
#                          (scipy.stats.skew / kurtosis with bias=False); 0 when
#                          the window has fewer than 4 samples or is constant
#   derivative             (last - first) / (t_last - t_first), per second
#   cov, corr              sample covariance (ddof = 1) and Pearson correlation
#                          between two channels; 0 when a channel is constant
#
# The device works in single precision, so values match the training features
# up to float32 rounding.

import math

# Minimum standard deviation for skewness and kurtosis (as in training).
_EPS = 1e-8


def _percentile(sorted_values, q):
    """Percentile q (0..1) of an already sorted list, linear interpolation."""
    n = len(sorted_values)
    pos = q * (n - 1)
    lo = int(pos)
    hi = lo + 1 if lo + 1 < n else n - 1
    return sorted_values[lo] + (pos - lo) * (sorted_values[hi] - sorted_values[lo])


def channel_stats(values, timestamps):
    """All the single-channel statistics of one window, as a dict.

    Keys are the attribute names used by ``model_input_array``; the mean is
    called ``average``.

    Missing statistics (empty window, or a single sample for the
    sample-based ones) are returned as 0.0, the value the model receives for
    a feature that cannot be computed.
    """
    n = len(values)
    st = {'average': 0.0, 'median': 0.0, 'std': 0.0, 'var': 0.0, 'max': 0.0,
          'min': 0.0, 'range': 0.0, 'p90': 0.0, 'energy': 0.0, 'iqr': 0.0,
          'skew': 0.0, 'kurt': 0.0, 'sma': 0.0, 'derivative': 0.0}
    if n == 0:
        return st

    # first pass: sums
    total = 0.0
    total_sq = 0.0
    total_abs = 0.0
    for x in values:
        total += x
        total_sq += x * x
        total_abs += abs(x)
    mean = total / n

    # second pass: central moments (two-pass for numerical stability)
    m2 = m3 = m4 = 0.0
    for x in values:
        d = x - mean
        d2 = d * d
        m2 += d2
        m3 += d2 * d
        m4 += d2 * d2

    s = sorted(values)
    st['average'] = mean
    st['max'] = s[-1]
    st['min'] = s[0]
    st['range'] = s[-1] - s[0]
    half = n // 2
    st['median'] = s[half] if n % 2 else (s[half - 1] + s[half]) / 2
    st['p90'] = _percentile(s, 0.9)
    st['iqr'] = _percentile(s, 0.75) - _percentile(s, 0.25)
    st['energy'] = total_sq / n
    st['sma'] = total_abs / n

    if n > 1:
        var = m2 / (n - 1)
        std = math.sqrt(var)
        st['var'] = var
        st['std'] = std
        dt = timestamps[-1] - timestamps[0]
        if dt:
            st['derivative'] = (values[-1] - values[0]) / dt * 1000.0
        # skewness and kurtosis: 0 for short or constant windows
        if n >= 4 and std >= _EPS and s[-1] != s[0]:
            b2 = m2 / n                      # biased variance
            g1 = (m3 / n) / (b2 ** 1.5)
            g2 = (m4 / n) / (b2 * b2) - 3.0
            st['skew'] = g1 * math.sqrt(n * (n - 1)) / (n - 2)
            st['kurt'] = (n - 1) / ((n - 2) * (n - 3)) * ((n + 1) * g2 + 6.0)
    return st


def _is_constant(v):
    return len(v) < 2 or max(v) == min(v)


def covariance(a, b):
    """Sample covariance (ddof = 1); 0 if a channel is constant."""
    n = min(len(a), len(b))
    if n < 2 or _is_constant(a[:n]) or _is_constant(b[:n]):
        return 0.0
    ma = sum(a[:n]) / n
    mb = sum(b[:n]) / n
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (n - 1)


def correlation(a, b):
    """Pearson correlation; 0 if a channel is constant."""
    n = min(len(a), len(b))
    if n < 2 or _is_constant(a[:n]) or _is_constant(b[:n]):
        return 0.0
    ma = sum(a[:n]) / n
    mb = sum(b[:n]) / n
    sab = saa = sbb = 0.0
    for i in range(n):
        da = a[i] - ma
        db = b[i] - mb
        sab += da * db
        saa += da * da
        sbb += db * db
    den = math.sqrt(saa * sbb)
    return sab / den if den > 0 else 0.0


class WindowFeatures:
    """Feature access for one window, in the form expected by
    ``model_input_array.build_input_array(g, vals, _cov, _corr)``.

    Statistics are computed lazily, once per channel, the first time any
    statistic of that channel is requested.
    """

    def __init__(self, timestamps, values):
        self.timestamps = timestamps
        self.values = values          # {channel: [values]}
        self._stats = {}

    def __len__(self):
        return len(self.timestamps)

    def vals(self, name):
        return self.values.get(name, [])

    def g(self, name, attr):
        st = self._stats.get(name)
        if st is None:
            st = channel_stats(self.vals(name), self.timestamps)
            self._stats[name] = st
        return st[attr]

    def input_array(self, builder):
        """Feature vector in model order. ``builder`` is
        ``model_input_array.build_input_array``."""
        return builder(self.g, self.vals, covariance, correlation)
