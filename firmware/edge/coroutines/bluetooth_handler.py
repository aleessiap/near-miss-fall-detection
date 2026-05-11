import aioble

# Function to scan for a specific Bluetooth device with the given MAC address and service UUID.
async def find_sensor(IMU_MAC_ADDRESS, IMU_SERVICE_UUID):
    while True:
        async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
            async for result in scanner:
                mac = ":".join("{:02X}".format(b) for b in result.device.addr)
                
                if mac == IMU_MAC_ADDRESS and IMU_SERVICE_UUID in result.services():
                    return result
    return None
