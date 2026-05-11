from collections import OrderedDict

# Custom ordered dictionary to maintain the order of keys
class CustomOrderDict(OrderedDict):
    def __str__(self):
        return "{" + ", ".join(f"{k}: {v}" for k, v in self.items()) + "}"

# Function to get an empty results dictionary with predefined keys
# The keys are the sensor data fields, initialized to 0
# Returns a CustomOrderDict with the keys and their initial values
def get_empty_results():
    return CustomOrderDict({
        "Timestamp": 0,
        "AccX": 0, "AccY": 0, "AccZ": 0,
        "GyroX": 0, "GyroY": 0, "GyroZ": 0,
        "AngX": 0, "AngY": 0, "AngZ": 0,
        "MagX": 0, "MagY": 0, "MagZ": 0,
    })
