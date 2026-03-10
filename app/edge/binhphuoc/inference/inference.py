import os
import sys
import time
import json
import base64
import random
from datetime import datetime, timezone
import numpy as np
import cv2
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
import torch
import torch.nn.functional as F
from torchvision import transforms
from PIL import Image
import timm

# Config
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt-broker-binhphuoc.default.svc")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MODEL_PATH = os.getenv("MODEL_PATH", "/model/fire_detection_best.pth")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))

# Expected frame shape
IMG_H, IMG_W, IMG_C = 224, 224, 3
FRAME_BYTES = IMG_H * IMG_W * IMG_C

preprocess = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

device = torch.device('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu')
model = None
class_names = []
last_alert_time = {}

LOCATIONS = {
    "hoanglienson": {"lat": 22.3964, "lon": 103.8200, "name": "Rừng quốc gia Hoàng Liên - Sa Pa, Lào Cai", "region": "north"},
    "bachma": {"lat": 16.0167, "lon": 107.8667, "name": "Vườn quốc gia Bạch Mã - Thừa Thiên Huế", "region": "central"},
    "dalat": {"lat": 11.8333, "lon": 108.4333, "name": "Rừng thông Đà Lạt - Lâm Đồng", "region": "south"}
}

def load_model():
    global model, class_names
    
    if not os.path.exists(MODEL_PATH):
        print(f"[ERROR] Checkpoint not found: {MODEL_PATH}")
        sys.exit(1)
        
    print(f"Loading checkpoint from: {MODEL_PATH} (Device: {device})")
    checkpoint = torch.load(MODEL_PATH, map_location=device, weights_only=False)
    
    class_names = checkpoint.get('class_names', ['fire', 'normal'])
    num_classes = len(class_names)
    model_name = checkpoint.get('model_name', "efficientnet_lite0") # Try reading from checkpoint, default to lite0
    
    print(f"Rebuilding architecture: {model_name} (Classes: {num_classes})")
    model = timm.create_model(model_name, pretrained=False, num_classes=num_classes)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"Connected to MQTT broker {MQTT_BROKER}:{MQTT_PORT}")
        # Use a shared subscription so Mosquitto load-balances frames across all Inference Pods
        client.subscribe("$share/edge_group/frames/#")
        print("Subscribed to $share/edge_group/frames/# (Shared Load Balancing)")
    else:
        print(f"[ERROR] MQTT connection failed: {reason_code}")

def on_message(client, userdata, msg):
    if len(msg.payload) != FRAME_BYTES:
        return
        
    topic_parts = msg.topic.split('/')
    camera_id = topic_parts[-1] if len(topic_parts) >= 2 else "unknown"

    # Decode RGB numpy array
    frame_rgb = np.frombuffer(msg.payload, dtype=np.uint8).reshape((IMG_H, IMG_W, IMG_C))
    input_tensor = preprocess(Image.fromarray(frame_rgb)).unsqueeze(0).to(device)
    
    # Run Inference
    t0 = time.time()
    with torch.no_grad():
        output = model(input_tensor)
        probs = F.softmax(output, dim=1)
        pred_class_idx = torch.argmax(probs, dim=1).item()
        confidence = probs[0][pred_class_idx].item()
    
    elapsed_ms = (time.time() - t0) * 1000.0
    detection_class = class_names[pred_class_idx]
    is_fire = (detection_class == "fire")
    
    prefix = "🔥 " if is_fire else "🌲 "
    print(f"[{camera_id}] {prefix}{detection_class.upper()} conf={confidence:.3f} (latency={elapsed_ms:.1f}ms)")
    
    # Generate Payload ONLY if fire is detected confidently
    if is_fire and confidence >= CONFIDENCE_THRESHOLD:
        current_time = time.time()
        # Throttling to send MQTT payloads at most once every 10 seconds per camera
        if camera_id in last_alert_time and current_time - last_alert_time[camera_id] < 10:
            return
        last_alert_time[camera_id] = current_time

        alert_id = f"alert_{int(time.time())}_{random.randint(100, 999)}"
        
        # BGR encoding for JPEG snapshot inside payload
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        _, buffer = cv2.imencode('.jpg', frame_bgr)
        b64_img = base64.b64encode(buffer.tobytes()).decode("utf-8")
        
        loc_data = LOCATIONS.get(camera_id, LOCATIONS["hoanglienson"])
        
        payload = {
            "alert_id": alert_id,
            "device_id": camera_id,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "location": {
                "lat": loc_data["lat"],
                "lon": loc_data["lon"],
                "name": loc_data["name"]
            },
            "region": loc_data["region"],
            "detections": [{"class": "fire", "confidence": confidence}],
            "confidence_max": confidence,
            "status": "active",
            "image_base64": b64_img
        }
        
        payload_json = json.dumps(payload)
        client.publish("wildfire/alerts", payload_json)
        print(f"  -> Dispatched ALERT {alert_id} payload to wildfire/alerts!")

def main():
    print("="*50)
    print("Edge PyTorch Inference Engine")
    print(f"Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Threshold: {CONFIDENCE_THRESHOLD}")
    print("="*50)
    
    load_model()

    client = mqtt.Client(CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
    except Exception as e:
        print(f"[ERROR] Failed to connect to broker: {e}")
        return

    client.loop_forever()

if __name__ == "__main__":
    main()
