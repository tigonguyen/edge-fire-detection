import os
import time
import json
import random
import base64
import random
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

import cv2
import numpy as np

# Env config
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt-broker-binhphuoc.default.svc")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
INTERVAL = int(os.getenv("INTERVAL_SECONDS", "30"))

def get_mock_image():
    img = np.zeros((224, 224, 3), dtype=np.uint8)
    img[:] = (0, 0, 255) # BGR format: Red
    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer.tobytes()).decode("utf-8")

def publish_mock_alert():
    alert_id = f"alert_{int(time.time())}_{random.randint(100, 999)}"
    device_id = f"edge_device_004"
    confidence = random.uniform(0.70, 0.95)
    
    # Matching the exact output of test_fire_alerts.py --test single --region north
    payload = {
        "alert_id": alert_id,
        "device_id": device_id,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "location": {
            "lat": 22.3964,
            "lon": 103.8200,
            "name": "Rừng quốc gia Hoàng Liên - Sa Pa, Lào Cai"
        },
        "region": "north",
        "detections": [
            {
                "class": "fire",
                "confidence": confidence
            }
        ],
        "confidence_max": confidence,
        "status": "active",
        "image_base64": get_mock_image()
    }
    
    payload_json = json.dumps(payload)
    
    print(f"[{datetime.now().isoformat()}] Preparing mock alert {alert_id}...")
    
    # 1. Connect
    client = mqtt.Client(CallbackAPIVersion.VERSION2)
    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
        print(f"Connected to {MQTT_BROKER}:{MQTT_PORT}")
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        return

    # 2. Publish
    info = client.publish("wildfire/alerts", payload_json)
    info.wait_for_publish()
    client.disconnect()
    
    print(f"[SUCCESS] Mock alert published to wildfire/alerts! Payload Size: {len(payload_json)} bytes")
    print(f"  - Alert ID: {alert_id}")
    print(f"  - Confidence: {confidence*100:.1f}%")
    print(f"  - Device: {device_id}")

def main():
    print("="*50)
    print("Python Inference Mock Layer (Direct Alert Mode)")
    print(f"Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Interval: {INTERVAL} seconds")
    print("="*50)
    
    while True:
        publish_mock_alert()
        print(f"Sleeping for {INTERVAL} seconds...\n")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
