import gc
import json
import sys
import bluetooth
import aioble
import uasyncio as asyncio
from lib.wifi_manager import WiFiManager
from lib.peripherals.led import TinyS3Led
from coroutines.data_processor import sensor_reader
from coroutines.save_data import append_to_json_file, get_unique_filename, save_data_processor
from lib.constants import get_empty_results
from coroutines.bluetooth_handler import find_sensor
from lib.Sensor_dimension import SensorDimension
from coroutines.preprocessor import preprocessor_coro
from coroutines.machine_learning_inference import processor_coro
from lib.primitives.queue import Queue
from coroutines.mqtt import mqtt_coro

print("Firmware starting...")

# Configuration file
_CFG_FILENAME = "config.json"


async def main_loop(cfg_dict: dict):

    IMU_SERVICE_UUID = bluetooth.UUID(cfg_dict["IMU_SERVICE"])
    IMU_CHAR_READ_UUID = bluetooth.UUID(cfg_dict["IMU_CHAR_READ"])
    IMU_CHAR_WRITE_UUID = bluetooth.UUID(cfg_dict["IMU_CHAR_WRITE"])
    print("IMU_SERVICE_UUID:", IMU_SERVICE_UUID)
    print("IMU_CHAR_READ_UUID:", IMU_CHAR_READ_UUID)
    print("IMU_CHAR_WRITE_UUID:", IMU_CHAR_WRITE_UUID)

    # Initialize the LED
    led = TinyS3Led()
    led.blue()

    # Initialize the list of coroutines to run
    coro_handles = []

    # Initialize the list of sensors and results
    sensors = []
    results = get_empty_results()

    # Create queues for communication between coroutines
    outgoing_mqtt_queue = Queue(maxsize=10)
    preprocessor_q = Queue(maxsize=100)  
    
    # wait for the IMU sensor to be found
    device = await find_sensor(cfg_dict["IMU_MAC_ADDRESS"], IMU_SERVICE_UUID)
    if device is None:
        print("IMU sensor not found")
        return
    else:
        print("IMU sensor found")

    try:
        # Connect to the IMU sensor
        connection = await device.device.connect()
    except asyncio.TimeoutError:
        print("Connection timeout")
        return
    async with connection:

        print("main_loop: IMU Connection context established")

        # Populate the sensors list with SensorDimension objects
        for dev_name in cfg_dict["data_to_analyze"]:
            sensors.append(SensorDimension(name=dev_name, buf_window_s=cfg_dict["WINDOW_SIZE"]))
        
        print("main_loop: sensors created:", [s.get_name() for s in sensors])
        
        # Set LED to green to indicate successful connection
        led.green()
        try:
            # Discover services and characteristics
            imu_service = await connection.service(IMU_SERVICE_UUID)
            imu_char_read = await imu_service.characteristic(IMU_CHAR_READ_UUID)
            imu_char_write = await imu_service.characteristic(IMU_CHAR_WRITE_UUID)
            await imu_char_read.subscribe(notify=True)

            # Task for reading sensor data
            sensor_reader_task = asyncio.create_task(sensor_reader(led, imu_char_read, imu_char_write, preprocessor_q, results))

            # Append the sensor reader task to the coroutine handles
            coro_handles.append(sensor_reader_task)
        
            # Check if we need to save data to a file
            if cfg_dict["register_data_mode"]:
                # Set LED to orange to indicate data registration mode
                led.orange()
                # Task for saving data to a file
                file_name = get_unique_filename()
                save_task = asyncio.create_task(save_data_processor(preprocessor_q, file_name))
                coro_handles.append(save_task)
            else:
                # Set LED to blue to indicate processing mode without data registration
                led.blue()
                print("main_loop: register_data_mode is False, not saving data to file")
                # Task for processing data without saving
                processables = []
                preprocessor_task = asyncio.create_task(preprocessor_coro(sensors, preprocessor_q, processables))
                coro_handles.append(preprocessor_task)

                # Task for machine learning inference
                processor_task = asyncio.create_task(processor_coro(processables, outgoing_mqtt_queue, my_id=cfg_dict["mqtt_client_id"])
                )
                coro_handles.append(processor_task)

                # Task for MQTT publishing
                mqtt_task = asyncio.create_task(mqtt_coro(outgoing_mqtt_queue, cfg_dict)
                )
                coro_handles.append(mqtt_task)
        
            await asyncio.gather(*coro_handles)

        except asyncio.TimeoutError:
            print("Timeout discovering services/characteristics")
            # Set LED to red to indicate error
            led.red()
            
        except aioble.DeviceDisconnectedError:
            print("Device Disconnected")
            # Set LED to red to indicate error
            led.red()


if __name__ == "__main__":
    # Enable garbage collector
    gc.enable()

    # Load configuration file
    cfg = {}

    try:
        with open(_CFG_FILENAME, 'r') as cfg_fp:
            cfg = json.load(cfg_fp)
            print("main: loaded config:\n", cfg)
    except:
        print("main: error while reading config file")
        sys.exit()


    # Establish WiFi connection and RTC sync
    print("Connecting to WiFi...")
    wm = WiFiManager(cfg["wifi_ssid"], cfg["wifi_pass"])
    wm.do_connect()
    wm.sync_RTC()

    # Run the control task
    try:
        asyncio.run(main_loop(cfg_dict=cfg))
    except KeyboardInterrupt:
        print('Interrupted')
    finally:
        asyncio.new_event_loop()  # Clear retained state

