import aioble


async def find_sensor(IMU_MAC_ADDRESS, IMU_SERVICE_UUID):
    """Scan until the IMU with the given MAC address and service is found.

    Returns the scan result of the sensor. The sensor accepts a single
    connection: it is not found while another device (e.g. the vendor app)
    is connected to it.
    """
    while True:
        async with aioble.scan(5000, interval_us=30000, window_us=30000, active=True) as scanner:
            async for result in scanner:
                mac = ":".join("{:02X}".format(b) for b in result.device.addr)
                if mac == IMU_MAC_ADDRESS and IMU_SERVICE_UUID in result.services():
                    return result
