# ══════════════════════════════════════════════════════════════════════════
# Final XGBoost model for the device: GENERATED AUTOMATICALLY by the training
# pipeline. Do not edit by hand: regenerate it from the training pipeline.
#
# Copy model_device.py, model_device.bin and model_input_array.py to the
# lib/ folder of the device. Usage in machine_learning_inference.py:
#     import lib.model_device as model
#     model.load('lib/model_device.bin')   # once, at start-up
#     pred = model.predict(input_array)    # 1 = near-miss, 0 = ADL
# input_array: the 53 RAW (unscaled) features in the order of FEATURES, built
# by model_input_array.build_input_array. The scaler is applied in this module.
MODEL_NAME = 'XGBoost'
# ══════════════════════════════════════════════════════════════════════════
import math
from array import array

N_FEATURES = 53
FEATURES = ['GyroX_mean', 'GyroX_skew', 'AccMag_derivative', 'GyroX_derivative', 'AngX_derivative', 'GyroY_derivative', 'AngMag_derivative', 'AccZ_derivative', 'GyroZ_mean', 'GyroZ_skew', 'AngY_derivative', 'Ang_corr_AngX_AngY', 'Ang_corr_AngX_AngZ', 'AngY_skew', 'AngY_kurt', 'AccX_derivative', 'Acc_cov_AccX_AccZ', 'Acc_cov_AccY_AccZ', 'Acc_corr_AccY_AccZ', 'AngX_skew', 'AngMag_skew', 'AngZ_kurt', 'AngX_kurt', 'Ang_cov_AngY_AngZ', 'AngZ_max', 'AngMag_min', 'AngY_energy', 'AngY_max', 'Gyro_corr_GyroX_GyroY', 'AccX_skew', 'Acc_corr_AccX_AccZ', 'Acc_corr_AccX_AccY', 'Gyro_cov_GyroX_GyroY', 'Gyro_corr_GyroX_GyroZ', 'GyroMag_skew', 'GyroY_kurt', 'GyroX_kurt', 'GyroZ_kurt', 'AccZ_skew', 'AccZ_kurt', 'AccY_median', 'AccY_skew', 'GyroY_min', 'GyroY_skew', 'Gyro_cov_GyroY_GyroZ', 'AngMag_range', 'AngX_min', 'AccY_range', 'AngX_std', 'AccX_kurt', 'GyroZ_derivative', 'AngZ_skew', 'AngZ_derivative']

# Numeric constants are stored as float32 bytes (little-endian) and read with
# array('f', ...): this keeps them EXACT in MicroPython, whose parser can get
# the last binary digit wrong when reading decimal numbers.

# StandardScaler: x_scaled = (x - MEAN) / SCALE, as in scikit-learn
MEAN = array('f', b'\xa9\x17`=\xec\xbc\x19>\xa8\xa6\xc3\xb76*w>4)\x13=\xbf/\x02>\xce\x9e\r\xbc\xbeh^:\x10*\xac\xbep\xe2\xff:4\xfa\xc7;%\x1f{=-\xa4\x10\xbdV\xc2\x98<HF\x13\xbd\xd8\x08\x00;\xca\x91\xb4:\x15s\x00;w(\xef<\xa7\xc2\xed\xbd\xe6\x8e\x1d;\xd9,\xe0\xbe\x91\xfd\x95\xbd\xf0\x18\x00\xbf(U\xdd@$\xde\xffB_\x81\xa1A\xc8\xa6\r@L\x829\xbds\x19\x82<y\x10\x1f\xbc\xdb\x14x<\x03\x85\xc5\xc2\xc6\x1bQ\xbdX\xd2\xf4>"\xd4\x9d\xbd\xa1h\xa8>kK\x01=\xe3\x97m>J\xd0*=:Rt?\x8d6\x17?$<\n\xc2}\x19\xa4<\xb3\x12,\xbf_1-A\xadv\xafB\xcc\n\x0b?J\xbf\xf7?\xd2Y\xc0>\xb6K\\\xbe\xd7\x85_<\xef\xd8\xbe;')
SCALE = array('f', b'\xbb\x8e"A\xce\x12m?MR\x85>\xceW\xceA\x1c\xa8\x82@[\xf4\tB[\x15\xfb@\xfc\xb8/>\xb0T\xcf@ `V?+J\x0b@\x7f\xe4\xf4>2X\xfa>\x16%D?\xe66\xd5?\xd9\xea/>\xa4\xb3\xd7=k:4>\xb0\x9f\x02?o\x8fM?cr??\xa7"\xe1?#\x89\xd9?`\xe5.B\x0c\xab\xcdB\xad\x9e\x07B\xc8\xc7\xe8A\xa5\xd7\x8d@\x90\x0f\xe8>\xdcSk?\xd7\x07\xfc>z\xba\xf1>\xb6\xa0\x06E%\xef\xf0>\xe1<^?g\x98\xe1?(-\xfa?\xecc\xea?d{S?\xd58\xef?\x03\xfb\xa5=\xd8\x8di?\x17\xae\xecAK`N?4\x9c@D\xd0\x956AC\x05cA\xfd4\x1b?s\x1e`@B7\xf3?\xd3\xaa\x9eAx\xe9C?\xdcE\x15B')

# Decision rule on the near-miss score: near-miss if score > THRESHOLD
# (THRESHOLD = 0.5)
THRESHOLD = array('f', b'\x00\x00\x00?')[0]

# Tree ensemble: N_NODES nodes in total, N_TREES trees.
# Tables loaded from model_device.bin (see load()).
N_NODES = 23150
N_TREES = 300
BASE_MARGIN = array('f', b'\x00\x00\x00\x00')[0]  # 0.0
_FEATURE = _THRESHOLD = _LEFT = _RIGHT = _ROOTS = None


def load(path='lib/' + 'model_device.bin'):
    """Load the tree tables from the binary file (little-endian)."""
    global _FEATURE, _THRESHOLD, _LEFT, _RIGHT, _ROOTS
    _FEATURE = array('h', bytes(2 * N_NODES))    # feature index, -1 = leaf
    _THRESHOLD = array('f', bytes(4 * N_NODES))  # split threshold, or leaf value
    _LEFT = array('i', bytes(4 * N_NODES))       # child when the condition is true
    _RIGHT = array('i', bytes(4 * N_NODES))      # child when the condition is false
    _ROOTS = array('i', bytes(4 * N_TREES))      # root node of each tree
    with open(path, 'rb') as f:
        for a in (_FEATURE, _THRESHOLD, _LEFT, _RIGHT, _ROOTS):
            f.readinto(a)


def score_scaled(x):
    """Near-miss score from ALREADY scaled features."""
    total = 0.0
    for r in _ROOTS:
        n = r
        while _FEATURE[n] >= 0:
            if x[_FEATURE[n]] < _THRESHOLD[n]:
                n = _LEFT[n]
            else:
                n = _RIGHT[n]
        total += _THRESHOLD[n]
    m = BASE_MARGIN + total
    # numerically stable sigmoid
    if m < 0:
        z = math.exp(m)
        return z / (1.0 + z)
    return 1.0 / (1.0 + math.exp(-m))


def scale(raw):
    """Apply the StandardScaler to the raw features."""
    if len(raw) != N_FEATURES:
        raise ValueError('expected %d features, got %d' % (N_FEATURES, len(raw)))
    return [(raw[i] - MEAN[i]) / SCALE[i] for i in range(N_FEATURES)]


def score(raw):
    """Near-miss score (higher = more likely near-miss) from the raw features."""
    return score_scaled(scale(raw))


def predict(raw):
    """1 = near-miss, 0 = ADL."""
    s = score(raw)
    return 1 if s > THRESHOLD else 0
