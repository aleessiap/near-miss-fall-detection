# ══════════════════════════════════════════════════════════════════════════
# Features of the final XGBoost model: GENERATED AUTOMATICALLY by the training
# pipeline. Do not edit by hand: regenerate it from the training pipeline.
#
# Usage in machine_learning_inference.py:
#     import lib.model_input_array as features
#     input_array = features.build_input_array(g, vals, _cov, _corr)
# ══════════════════════════════════════════════════════════════════════════
import math

# Sensor channels used by the features: all of them must be computed and
# buffered by the firmware. Check them at start-up: g() returns 0.0 without
# any error if a channel is missing.
REQUIRED_DIMENSIONS = ['GyroX', 'AccMag', 'AngX', 'GyroY', 'AngMag', 'AccZ', 'GyroZ', 'AngY', 'AngZ', 'AccX', 'AccY', 'GyroMag']

N_FEATURES = 53


def _mean_vector_angle(xs, ys, zs):
    """Angle (degrees) between the mean vector of the window and the Z axis,
    as mean_vector_angle in the training feature extraction. 0.0 if the
    vector is null."""
    n = min(len(xs), len(ys), len(zs))
    if n == 0:
        return 0.0
    mx = sum(xs[:n]) / n
    my = sum(ys[:n]) / n
    mz = sum(zs[:n]) / n
    norm = (mx * mx + my * my + mz * mz) ** 0.5
    if norm == 0:
        return 0.0
    c = max(-1.0, min(1.0, mz / norm))
    return math.degrees(math.acos(c))


def build_input_array(g, vals, _cov, _corr):
    """input_array in the feature order of the model (RAW features: the
    scaler is applied by model_device.predict)."""
    return [
        g('GyroX', 'average'),                               # f0: GyroX_mean
        g('GyroX', 'skew'),                                  # f1: GyroX_skew
        g('AccMag', 'derivative'),                           # f2: AccMag_derivative
        g('GyroX', 'derivative'),                            # f3: GyroX_derivative
        g('AngX', 'derivative'),                             # f4: AngX_derivative
        g('GyroY', 'derivative'),                            # f5: GyroY_derivative
        g('AngMag', 'derivative'),                           # f6: AngMag_derivative
        g('AccZ', 'derivative'),                             # f7: AccZ_derivative
        g('GyroZ', 'average'),                               # f8: GyroZ_mean
        g('GyroZ', 'skew'),                                  # f9: GyroZ_skew
        g('AngY', 'derivative'),                             # f10: AngY_derivative
        _corr(vals('AngX'), vals('AngY')),                   # f11: Ang_corr_AngX_AngY
        _corr(vals('AngX'), vals('AngZ')),                   # f12: Ang_corr_AngX_AngZ
        g('AngY', 'skew'),                                   # f13: AngY_skew
        g('AngY', 'kurt'),                                   # f14: AngY_kurt
        g('AccX', 'derivative'),                             # f15: AccX_derivative
        _cov(vals('AccX'), vals('AccZ')),                    # f16: Acc_cov_AccX_AccZ
        _cov(vals('AccY'), vals('AccZ')),                    # f17: Acc_cov_AccY_AccZ
        _corr(vals('AccY'), vals('AccZ')),                   # f18: Acc_corr_AccY_AccZ
        g('AngX', 'skew'),                                   # f19: AngX_skew
        g('AngMag', 'skew'),                                 # f20: AngMag_skew
        g('AngZ', 'kurt'),                                   # f21: AngZ_kurt
        g('AngX', 'kurt'),                                   # f22: AngX_kurt
        _cov(vals('AngY'), vals('AngZ')),                    # f23: Ang_cov_AngY_AngZ
        g('AngZ', 'max'),                                    # f24: AngZ_max
        g('AngMag', 'min'),                                  # f25: AngMag_min
        g('AngY', 'energy'),                                 # f26: AngY_energy
        g('AngY', 'max'),                                    # f27: AngY_max
        _corr(vals('GyroX'), vals('GyroY')),                 # f28: Gyro_corr_GyroX_GyroY
        g('AccX', 'skew'),                                   # f29: AccX_skew
        _corr(vals('AccX'), vals('AccZ')),                   # f30: Acc_corr_AccX_AccZ
        _corr(vals('AccX'), vals('AccY')),                   # f31: Acc_corr_AccX_AccY
        _cov(vals('GyroX'), vals('GyroY')),                  # f32: Gyro_cov_GyroX_GyroY
        _corr(vals('GyroX'), vals('GyroZ')),                 # f33: Gyro_corr_GyroX_GyroZ
        g('GyroMag', 'skew'),                                # f34: GyroMag_skew
        g('GyroY', 'kurt'),                                  # f35: GyroY_kurt
        g('GyroX', 'kurt'),                                  # f36: GyroX_kurt
        g('GyroZ', 'kurt'),                                  # f37: GyroZ_kurt
        g('AccZ', 'skew'),                                   # f38: AccZ_skew
        g('AccZ', 'kurt'),                                   # f39: AccZ_kurt
        g('AccY', 'median'),                                 # f40: AccY_median
        g('AccY', 'skew'),                                   # f41: AccY_skew
        g('GyroY', 'min'),                                   # f42: GyroY_min
        g('GyroY', 'skew'),                                  # f43: GyroY_skew
        _cov(vals('GyroY'), vals('GyroZ')),                  # f44: Gyro_cov_GyroY_GyroZ
        g('AngMag', 'range'),                                # f45: AngMag_range
        g('AngX', 'min'),                                    # f46: AngX_min
        g('AccY', 'range'),                                  # f47: AccY_range
        g('AngX', 'std'),                                    # f48: AngX_std
        g('AccX', 'kurt'),                                   # f49: AccX_kurt
        g('GyroZ', 'derivative'),                            # f50: GyroZ_derivative
        g('AngZ', 'skew'),                                   # f51: AngZ_skew
        g('AngZ', 'derivative'),                             # f52: AngZ_derivative
    ]
