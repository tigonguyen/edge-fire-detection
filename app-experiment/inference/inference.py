import os
import sys
import time
import json
import base64
import random
import struct
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
MQTT_BROKER = os.getenv("MQTT_BROKER", "edge-fire-mqtt.default.svc")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MODEL_PATH = os.getenv("MODEL_PATH", "/model/fire_detection_best.pth")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))

# Expected frame shape
IMG_H, IMG_W, IMG_C = 224, 224, 3
FRAME_BYTES = IMG_H * IMG_W * IMG_C
TIMESTAMP_BYTES = 8

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
    model_name = checkpoint.get('model_name', "efficientnet_lite0")
    
    print(f"Rebuilding architecture: {model_name} (Classes: {num_classes})")
    model = timm.create_model(model_name, pretrained=False, num_classes=num_classes)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"Connected to MQTT broker {MQTT_BROKER}:{MQTT_PORT}")
        # Subscribe to experiment topic exclusively
        client.subscribe("$share/experiment_group/experiment/#")
        print("Subscribed to $share/experiment_group/experiment/#")
    else:
        print(f"[ERROR] MQTT connection failed: {reason_code}")

def on_message(client, userdata, msg):
    if len(msg.payload) != FRAME_BYTES + TIMESTAMP_BYTES:
        return
        
    topic_parts = msg.topic.split('/')
    camera_id = topic_parts[-1] if len(topic_parts) >= 2 else "unknown"

    # --- LATENCY CALCULATION ---
    frame_data = msg.payload[:FRAME_BYTES]
    timestamp_data = msg.payload[FRAME_BYTES:]
    send_time = struct.unpack('d', timestamp_data)[0]
    
    received_time = time.time()
    network_latency = (received_time - send_time) * 1000.0

    # Decode RGB numpy array
    frame_rgb = np.frombuffer(frame_data, dtype=np.uint8).reshape((IMG_H, IMG_W, IMG_C))
    input_tensor = preprocess(Image.fromarray(frame_rgb)).unsqueeze(0).to(device)
    
    # Run Inference
    t0 = time.time()
    with torch.no_grad():
        output = model(input_tensor)
        probs = F.softmax(output, dim=1)
        pred_class_idx = torch.argmax(probs, dim=1).item()
        confidence = probs[0][pred_class_idx].item()
    
    inference_latency = (time.time() - t0) * 1000.0
    total_latency = (time.time() - send_time) * 1000.0
    
    detection_class = class_names[pred_class_idx]
    
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.85"))
    
    is_fire = (detection_class == "fire")
    if is_fire and confidence < CONFIDENCE_THRESHOLD:
        is_fire = False
        detection_class = "normal (suppressed)"
    
    prefix = "🔥 " if is_fire else "🌲 "
    
    # FORMATTED LATENCY LOG FOR EXPERIMENT
    print(f"[{camera_id}] {prefix}{detection_class.upper()} conf={confidence:.3f} | Net: {network_latency:.1f}ms | Inf: {inference_latency:.1f}ms | Total: {total_latency:.1f}ms")
    
    # Skip alert dispatching for experiment speed
    pass

def main():
    print("="*50)
    print("Edge PyTorch Inference Engine (EXPERIMENT MODE)")
    print(f"Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Threshold: {CONFIDENCE_THRESHOLD}")
    print("="*50)
    
    load_model()

    client = mqtt.Client(CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)
    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT)
            break
        except Exception as e:
            print(f"[ERROR] Failed to connect to broker: {e}. Retrying...")
            time.sleep(5)

    client.loop_forever()

if __name__ == "__main__":
    main()
