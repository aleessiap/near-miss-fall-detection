import struct
import time, asyncio

initial_timestamp = None
# Function to convert a byte array to a signed integer
def _get_signed_int(data):
    return struct.unpack("<h", bytes(data))[0]

# Function to update the timestamp in the results dictionary
def update_timestamp(results):
    global initial_timestamp
    if initial_timestamp is None:
        initial_timestamp = time.time_ns() // 1_000_000
    now = time.time_ns() // 1_000_000
    results["Timestamp"] = now - initial_timestamp

# Function to decode IMU data and update the results dictionary
async def decode_imu_data(imu_char_read, results):
    data = await imu_char_read.notified()
    if len(data) == 20:
        results["AccX"] = _get_signed_int(data[2:4]) / 32768 * 16
        results["AccY"] = _get_signed_int(data[4:6]) / 32768 * 16
        results["AccZ"] = _get_signed_int(data[6:8]) / 32768 * 16
        results["GyroX"] = _get_signed_int(data[8:10]) / 32768 * 2000
        results["GyroY"] = _get_signed_int(data[10:12]) / 32768 * 2000
        results["GyroZ"] = _get_signed_int(data[12:14]) / 32768 * 2000
        results["AngX"] = _get_signed_int(data[14:16]) / 32768 * 180
        results["AngY"] = _get_signed_int(data[16:18]) / 32768 * 180
        results["AngZ"] = _get_signed_int(data[18:20]) / 32768 * 180

# Function to decode magnetometer data and update the results dictionary
async def decode_magnetometer_data(imu_char_read, results):
    data = await imu_char_read.notified()
    if len(data) >= 10:
        results["MagX"] = _get_signed_int(data[4:6]) / 120
        results["MagY"] = _get_signed_int(data[6:8]) / 120
        results["MagZ"] = _get_signed_int(data[8:10]) / 120

# Coroutine to read sensor data and update the results dictionary
# It reads data from the IMU and magnetometer, updates the timestamp, and puts the results in the processor queue
# The results dictionary is initialized with empty values for each sensor dimension
# The coroutine runs indefinitely, reading data and updating the results at regular intervals
async def sensor_reader(led, imu_char_read, imu_char_write, processor_q, results):
    while True:
        led.blue()
        update_timestamp(results)
        await decode_imu_data(imu_char_read, results)
        
        await imu_char_write.write(bytes([0xFF, 0xAA, 0x27, 0x3A, 0x00]))
        await decode_magnetometer_data(imu_char_read, results)

        await processor_q.put(results.copy())
        await asyncio.sleep(0.1)



