# coroutines/mqtt.py
import urequests
import time
import uasyncio as asyncio
from umqtt.simple import MQTTClient
import json


def make_callback(cfg):
    """
    Returns a callback function for MQTT messages.
    The callback function processes incoming MQTT messages, extracts the data,
    and sends it to the cloud API.
    """
    def callback(topic, msg):
        try:
            topic_str = topic.decode()
            msg_str = msg.decode()

            print(f"MQTT RECEVEID from: {topic_str}, message: {msg_str}")

            data = json.loads(msg_str)
            data["token"] = cfg["api_token"]

            print("MQTT message received:", data)

            if not all(k in data for k in ("token","eventType", "timestamp", "sensorId")):
                print("MQTT message is malformed: missing required fields.")
                return
            if isinstance(data.get("timestamp"), int):
                t = time.gmtime(data["timestamp"])
                data["timestamp"] = "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z".format(t[0], t[1], t[2], t[3], t[4], t[5])
            

            url = cfg["cloud_api"]
            print(f"POST to {url} with data: {data}")
            # Invia alla cloud API
            headers = {"Content-Type": "application/json"}
            response = urequests.post(url, json=data, headers=headers)
            print(f"POST to {url} → {response.status_code} response: {response.text}")
            response.close()

        except Exception as e:
            print(f"Error in the MQTT callback: {e}")

    return callback

# Coroutine to handle MQTT subscriptions and incoming messages
async def mqtt_coro(cfg):
    client = MQTTClient(
        client_id=cfg["mqtt_client_id"], 
        server=cfg["mqtt_broker"],
        port=cfg.get("mqtt_port", 1883),
        user=cfg.get("mqtt_user"),
        password=cfg.get("mqtt_password"),
        keepalive=60
    )

    # Get the list of topics to subscribe to from the configuration
    topics = cfg.get("mqtt_topic_operators", [])

    try:
        # Set the callback function for incoming MQTT messages
        client.set_callback(make_callback(cfg))
        client.connect()
        print("mqtt_coro: connected to broker")

        # Subscribe to the specified topics
        for topic in topics:
            client.subscribe(topic.encode())
            print(f"mqtt_coro: subscribed to topic {topic}")

    except Exception as e:
        print("mqtt_coro: connection error:", e)
        return

    while True:
        try:
            # Check for incoming MQTT messages and call the callback function
            client.check_msg()
           
        except Exception as e:
            print(f"Errore check_msg: {e}")
        await asyncio.sleep(0.1)  # non saturare la CPU
