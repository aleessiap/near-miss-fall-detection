from lib.primitives.queue import Queue
import uasyncio
import time
import lib.model as model


def _cov(a, b):
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    ma = sum(a[:n]) / n
    mb = sum(b[:n]) / n
    return sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (n - 1)


def _corr(a, b):
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    ma = sum(a[:n]) / n
    mb = sum(b[:n]) / n
    da = [x - ma for x in a[:n]]
    db = [x - mb for x in b[:n]]
    std_a = (sum(x * x for x in da) / (n - 1)) ** 0.5
    std_b = (sum(x * x for x in db) / (n - 1)) ** 0.5
    if std_a < 1e-8 or std_b < 1e-8:
        return 0.0
    return sum(da[i] * db[i] for i in range(n)) / ((n - 1) * std_a * std_b)


async def processor_coro(
        processables: list,
        outgoing_mqtt_queue:Queue,
        my_id: str
        ):
    print("processor_coro: Inside processor coro. Waiting for an input")

    await uasyncio.sleep_ms(5000)
    print("processor_coro: Starting main loop")
    while True:
        await uasyncio.sleep_ms(1000)
        if processables != []:

            # Map sensor name to processable for direct access
            sm = {p.raw_device_name: p for p in processables}

            def g(name, attr):
                s = sm.get(name)
                return getattr(s, attr, 0.0) or 0.0

            def vals(name):
                s = sm.get(name)
                return s.raw_device.get_window_values() if s else []

            # Build the 90-feature input vector in the exact order used during training
            # (order from selected_features5_soglia50.csv — cv_fold1)
            input_array = [
                g('MagZ',      'derivative'),                    # f0: MagZ_derivative
                g('MagY',      'derivative'),                    # f1: MagY_derivative
                g('MagX',      'derivative'),                    # f2: MagX_derivative
                g('AngZ',      'derivative'),                    # f3: AngZ_derivative
                g('GyroY',     'derivative'),                    # f4: GyroY_derivative
                g('AngZ',      'skew'),                          # f5: AngZ_skew
                g('GyroX',     'average'),                       # f6: GyroX_mean
                g('GyroX',     'skew'),                          # f7: GyroX_skew
                g('GyroMag',   'derivative'),                    # f8: GyroMag_derivative
                g('AngX',      'derivative'),                    # f9: AngX_derivative
                g('AngMag',    'derivative'),                    # f10: AngMag_derivative
                g('AccZ',      'derivative'),                    # f11: AccZ_derivative
                g('AccX',      'derivative'),                    # f12: AccX_derivative
                _cov( vals('AccX'),      vals('AccZ')),          # f13: Acc_cov_AccX_AccZ
                g('AccY',      'derivative'),                    # f14: AccY_derivative
                g('GyroX',     'derivative'),                    # f15: GyroX_derivative
                g('GyroZ',     'derivative'),                    # f16: GyroZ_derivative
                _corr(vals('GyroX'),     vals('GyroY')),         # f17: Gyro_corr_GyroX_GyroY
                _corr(vals('AngX'),      vals('AngZ')),          # f18: Ang_corr_AngX_AngZ
                _corr(vals('AngX'),      vals('AngY')),          # f19: Ang_corr_AngX_AngY
                g('AccX',      'skew'),                          # f20: AccX_skew
                _corr(vals('AccX'),      vals('AccZ')),          # f21: Acc_corr_AccX_AccZ
                _corr(vals('AccX'),      vals('AccY')),          # f22: Acc_corr_AccX_AccY
                g('GyroZ',     'average'),                       # f23: GyroZ_mean
                g('GyroZ',     'skew'),                          # f24: GyroZ_skew
                g('AngY',      'derivative'),                    # f25: AngY_derivative
                g('AngX',      'skew'),                          # f26: AngX_skew
                g('AngMag',    'skew'),                          # f27: AngMag_skew
                g('AngZ',      'kurt'),                          # f28: AngZ_kurt
                g('AngMag',    'kurt'),                          # f29: AngMag_kurt
                g('AngX',      'kurt'),                          # f30: AngX_kurt
                _cov( vals('AngY'),      vals('AngZ')),          # f31: Ang_cov_AngY_AngZ
                _corr(vals('AngY'),      vals('AngZ')),          # f32: Ang_corr_AngY_AngZ
                g('AngY',      'kurt'),                          # f33: AngY_kurt
                g('GyroY',     'average'),                       # f34: GyroY_mean
                g('GyroY',     'skew'),                          # f35: GyroY_skew
                g('MagZ',      'skew'),                          # f36: MagZ_skew
                _corr(vals('MagX_norm'), vals('MagY_norm')),     # f37: Mag_norm_corr_MagX_norm_MagY_norm
                g('MagX_norm', 'median'),                        # f38: MagX_norm_median
                g('MagX_norm', 'kurt'),                          # f39: MagX_norm_kurt
                g('MagZ_norm', 'kurt'),                          # f40: MagZ_norm_kurt
                g('MagZ_norm', 'range'),                         # f41: MagZ_norm_range
                g('MagZ_norm', 'min'),                           # f42: MagZ_norm_min
                g('AngY',      'energy'),                        # f43: AngY_energy
                g('AngY',      'max'),                           # f44: AngY_max
                g('AngMag',    'min'),                           # f45: AngMag_min
                g('AngZ',      'range'),                         # f46: AngZ_range
                g('AngZ',      'max'),                           # f47: AngZ_max
                _corr(vals('MagX'),      vals('MagZ')),          # f48: Mag_corr_MagX_MagZ
                g('MagX',      'range'),                         # f49: MagX_range
                g('MagX',      'min'),                           # f50: MagX_min
                g('MagX',      'median'),                        # f51: MagX_median
                g('MagX',      'skew'),                          # f52: MagX_skew
                _cov( vals('AccY'),      vals('AccZ')),          # f53: Acc_cov_AccY_AccZ
                _corr(vals('AccY'),      vals('AccZ')),          # f54: Acc_corr_AccY_AccZ
                g('AccZ',      'skew'),                          # f55: AccZ_skew
                g('AccZ',      'kurt'),                          # f56: AccZ_kurt
                _cov( vals('GyroX'),     vals('GyroY')),         # f57: Gyro_cov_GyroX_GyroY
                _cov( vals('GyroX'),     vals('GyroZ')),         # f58: Gyro_cov_GyroX_GyroZ
                _corr(vals('GyroX'),     vals('GyroZ')),         # f59: Gyro_corr_GyroX_GyroZ
                g('AccY',      'median'),                        # f60: AccY_median
                g('AccY',      'skew'),                          # f61: AccY_skew
                g('MagX_norm', 'p90'),                           # f62: MagX_norm_p90
                g('MagMag',    'min'),                           # f63: MagMag_min
                g('AngX',      'var'),                           # f64: AngX_var
                _cov( vals('GyroY'),     vals('GyroZ')),         # f65: Gyro_cov_GyroY_GyroZ
                _corr(vals('GyroY'),     vals('GyroZ')),         # f66: Gyro_corr_GyroY_GyroZ
                g('AngMag',    'std'),                           # f67: AngMag_std
                g('MagY_norm', 'range'),                         # f68: MagY_norm_range
                g('AngX',      'min'),                           # f69: AngX_min
                g('AccZ',      'min'),                           # f70: AccZ_min
                g('AccY',      'range'),                         # f71: AccY_range
                g('AccX',      'range'),                         # f72: AccX_range
                g('AccZ',      'range'),                         # f73: AccZ_range
                g('AccZ',      'iqr'),                           # f74: AccZ_iqr
                g('GyroMag',   'max'),                           # f75: GyroMag_max
                g('GyroX',     'range'),                         # f76: GyroX_range
                g('AngY',      'range'),                         # f77: AngY_range
                g('AngX',      'std'),                           # f78: AngX_std
                g('AccX',      'iqr'),                           # f79: AccX_iqr
                g('GyroMag',   'median'),                        # f80: GyroMag_median
                g('GyroY',     'min'),                           # f81: GyroY_min
                g('GyroZ',     'max'),                           # f82: GyroZ_max
                g('AccY',      'min'),                           # f83: AccY_min
                g('GyroMag',   'skew'),                          # f84: GyroMag_skew
                g('GyroY',     'kurt'),                          # f85: GyroY_kurt
                g('GyroX',     'kurt'),                          # f86: GyroX_kurt
                g('GyroZ',     'kurt'),                          # f87: GyroZ_kurt
                g('AccX',      'kurt'),                          # f88: AccX_kurt
                g('AngY',      'skew'),                          # f89: AngY_skew
            ]

            if input_array != []:
                # Pass the input array to the model for prediction
                pred = model.predict(input_array)
                # Debugging output
                if pred != 1 and pred != 0:
                    print("processor_coro: error in label")
                    continue
                # If the prediction is 1, it indicates a near miss
                if pred == 1:
                    print("processor_coro: Near Miss detected")
                    await outgoing_mqtt_queue.put({
                        "eventType": "near_miss",
                        "timestamp": time.time(),
                        "sensorId": my_id
                    })
            