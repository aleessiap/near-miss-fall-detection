# coroutines/mqtt.py

import uasyncio as asyncio
from umqtt.simple import MQTTClient
import json

# Coroutine to handle MQTT publishing
async def mqtt_coro(mqtt_queue, cfg):
    client = MQTTClient(
        client_id=cfg["mqtt_client_id"], 
        server=cfg["mqtt_broker"],
        port=cfg.get("mqtt_port", 1883),
        user=cfg.get("mqtt_user"),
        password=cfg.get("mqtt_password"),
        keepalive=60
    )

    try:
        # Connect to the MQTT broker
        client.connect()
        print("mqtt_coro: connected to broker")
    except Exception as e:
        print("mqtt_coro: connection error:", e)
        return

    while True:
        try:
            # Wait for a message to publish
            msg = await mqtt_queue.get()
            topic = cfg.get("mqtt_topic", "tinys3/events")
            payload = json.dumps(msg)
            client.publish(topic, payload)
            print(f"mqtt_coro: published: {payload}")
        except Exception as e:
            print("mqtt_coro: publish error:", e)
        await asyncio.sleep(0.1)  # non saturare la CPU
