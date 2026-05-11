
from lib.windowedCircularBuffer import WindowedCircularBuffer
import math

# Class representing a sensor dimension with a circular buffer for data storage
# It allows updating values, retrieving statistics, and managing the buffer
# The buffer length and window size can be specified during initialization
class SensorDimension:
    def __init__(self, name: str,  buf_len = 30, buf_window_s = 2):
        self._name = name
        self._buffer = WindowedCircularBuffer(buf_len, buf_window_s)
        
    # Function to update the value in the buffer
    # It appends the value with the current timestamp to the buffer
    # The timestamp is used to manage the circular buffer and ensure data is within the specified window
    # The value is appended to the buffer, which manages the circular nature of the data storage
    def update_value(self, value: float, timestamp: int):
        self._buffer.append(value, timestamp)

    # Function to get the name of the sensor dimension
    # Returns the name of the sensor dimension
    # This is used to identify the sensor in the system
    def get_name(self) -> str:
        """Returns the sensor dimension."""
        return self._name
    
    # Function to get the average value in the buffer
    # If the buffer is empty, it returns None
    # The average is calculated from the values in the current window of the buffer
    # Returns the average value of the values in the buffer
    def get_avg(self):
        return self._buffer.get_window_mean()

    # Function to get the standard deviation of the values in the buffer
    # If the buffer is empty, it returns None
    # The standard deviation is calculated from the values in the current window of the buffer
    # Returns the standard deviation of the values in the buffer
    def get_std(self):
        data = self._buffer.get_window_values()
        n = len(data)
        if n < 2:
            return None
        mean = sum(data) / n
        return (sum((x - mean) ** 2 for x in data) / (n - 1)) ** 0.5

    # Function to get the minimum value in the buffer
    # If the buffer is empty, it returns None
    # The minimum value is calculated from the values in the current window of the buffer
    def get_min(self):
        data = self._buffer.get_window_values()
        if not data:
            return None
        return min(data)
    
    # Function to get the maximum value in the buffer
    # If the buffer is empty, it returns None
    # The maximum value is calculated from the values in the current window of the buffer
    def get_max(self):
        data = self._buffer.get_window_values()
        if not data:
            return None
        return max(data)
 
    # Function to get the range of values in the buffer
    # The range is calculated as the difference between the maximum and minimum values
    # If the buffer is empty, it returns None
    def get_range(self):
        min_val = self.get_min()
        max_val = self.get_max()
        if min_val is None or max_val is None:
            return None
        return max_val - min_val
    
    # Function to get the derivative of the values in the buffer
    # The derivative is calculated as the change in value over the change in time
    # If there are not enough values to calculate the derivative, it returns None
    # Returns the derivative of the values in the buffer
    def get_derivative(self):
        values, timestamps = self._buffer.get_window()
        if len(values) < 2 or len(timestamps) < 2:
            return None
        # newest first: values[0]=newest, values[-1]=oldest
        dt = timestamps[0] - timestamps[-1]  # ms
        if dt == 0:
            return None
        return (values[0] - values[-1]) / dt * 1000  # per second

    # Function to get all values in the current window of the buffer
    # Returns the list of values currently stored in the active window
    def get_window_values(self):
        return self._buffer.get_window_values()

    # Function to get the median value in the buffer
    # If the buffer is empty, it returns None
    # The median is calculated from the sorted values in the current window of the buffer
    # Returns the central value, or the average of the two central values if the number of elements is even
    def get_median(self):
        data = self._buffer.get_window_values()
        if not data:
            return None
        s = sorted(data)
        n = len(s)
        mid = n // 2
        return (s[mid] + s[mid - 1]) / 2 if n % 2 == 0 else s[mid]
    
    # Function to get the variance of the values in the buffer
    # If there are fewer than 2 values, it returns None
    # The variance is calculated from the values in the current window of the buffer
    # Returns the variance of the values in the buffer
    def get_var(self):
        data = self._buffer.get_window_values()
        n = len(data)
        if n < 2:
            return None
        mean = sum(data) / n
        return sum((x - mean) ** 2 for x in data) / (n - 1)

    # Function to get the interquartile range (IQR) of the values in the buffer
    # If the buffer is empty, it returns None
    # The IQR is calculated as the difference between the 75th percentile and the
    # 25th percentile of the values in the current window of the buffer
    # Returns the interquartile range of the values in the buffer
    def get_iqr(self):
        data = self._buffer.get_window_values()
        if not data:
            return None
        s = sorted(data)
        n = len(s)
        def pct(p):
            idx = p * (n - 1)
            lo, hi = int(idx), min(int(idx) + 1, n - 1)
            return s[lo] + (idx - lo) * (s[hi] - s[lo])
        return pct(0.75) - pct(0.25)

    # Function to get the 90th percentile (P90) of the values in the buffer
    # If the buffer is empty, it returns None
    # The P90 is calculated from the sorted values in the current window of the buffer
    # Returns the value below which 90% of the values in the buffer fall
    def get_p90(self):
        data = self._buffer.get_window_values()
        if not data:
            return None
        s = sorted(data)
        n = len(s)
        idx = 0.9 * (n - 1)
        lo, hi = int(idx), min(int(idx) + 1, n - 1)
        return s[lo] + (idx - lo) * (s[hi] - s[lo])

    # Function to get the energy of the values in the buffer
    # If the buffer is empty, it returns None
    # The energy is calculated as the mean of the squared values in the current window of the buffer
    # Returns the average signal energy of the values in the buffer
    def get_energy(self):
        data = self._buffer.get_window_values()
        if not data:
            return None
        return sum(x * x for x in data) / len(data)

    # Function to get the skewness of the values in the buffer
    # If there are fewer than 4 values, it returns 0.0
    # Skewness measures the asymmetry of the value distribution in the current window
    # If the standard deviation is too small, it returns 0.0
    # Returns the skewness of the values in the buffer
    def get_skew(self):
        data = self._buffer.get_window_values()
        n = len(data)
        if n < 4:
            return 0.0
        mean = sum(data) / n
        devs = [x - mean for x in data]
        var = sum(d * d for d in devs) / n
        std = var ** 0.5
        if std < 1e-8:
            return 0.0
        biased = sum(d ** 3 for d in devs) / (n * std ** 3)
        return biased * (n * (n - 1)) ** 0.5 / (n - 2)

    # Function to get the kurtosis of the values in the buffer
    # If there are fewer than 4 values, it returns 0.0
    # Kurtosis measures the tailedness of the value distribution in the current window
    # If the standard deviation is too small, it returns 0.0
    # Returns the excess kurtosis of the values in the buffer
    def get_kurt(self):
        data = self._buffer.get_window_values()
        n = len(data)
        if n < 4:
            return 0.0
        mean = sum(data) / n
        devs = [x - mean for x in data]
        var = sum(d * d for d in devs) / n
        std = var ** 0.5
        if std < 1e-8:
            return 0.0
        biased = sum(d ** 4 for d in devs) / (n * std ** 4) - 3.0
        return (n - 1) / ((n - 2) * (n - 3)) * ((n + 1) * biased + 6)
    
    # Function to get the signal magnitude area-like measure of the values in the buffer
    # If the buffer is empty, it returns 0.0
    # The value is calculated as the mean of the absolute values in the current window of the buffer
    # Returns the average absolute magnitude of the values in the buffer
    def get_sma(self):
        data = self._buffer.get_window_values()
        if not data:
            return 0.0
        return sum(abs(x) for x in data) / len(data)

