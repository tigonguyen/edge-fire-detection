import os
import sys
import time
import numpy as np
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
import torch
import torch.nn.functional as F
from torchvision import transforms
from PIL import Image

# Import timm to instantiate EfficientNet-Lite0
import timm

# Config
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MODEL_PATH = os.getenv("MODEL_PATH", "../fire_detection_best.pth")

# Expected frame shape
IMG_H, IMG_W, IMG_C = 224, 224, 3
FRAME_BYTES = IMG_H * IMG_W * IMG_C

# PyTorch transformation (identical to training/testing)
preprocess = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

device = torch.device('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu')
model = None
class_names = []

def load_model():
    global model, class_names
    
    if not os.path.exists(MODEL_PATH):
        print(f"[ERROR] Checkpoint not found: {MODEL_PATH}")
        sys.exit(1)
        
    print(f"Loading checkpoint from: {MODEL_PATH} (Device: {device})")
    checkpoint = torch.load(MODEL_PATH, map_location=device, weights_only=False)
    
    class_names = checkpoint.get('class_names', ['fire', 'normal'])
    num_classes = len(class_names)
    
    # Checkpoint was trained as EfficientNet-B0 (has SE blocks), not Lite0
    model_name = "efficientnet_b0"
    
    print(f"Rebuilding architecture: {model_name} (Classes: {num_classes})")
    model = timm.create_model(model_name, pretrained=False, num_classes=num_classes)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()
    
    print(f"✅ Model loaded. Epoch: {checkpoint.get('epoch', 'N/A')}, Val Accuracy: {checkpoint.get('val_acc', 'N/A')}%")

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"Connected to MQTT broker {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe("frames/#")
        print("Subscribed to frames/#")
    else:
        print(f"[ERROR] MQTT connection failed: {reason_code}")

def on_message(client, userdata, msg):
    if len(msg.payload) != FRAME_BYTES:
        return
        
    topic_parts = msg.topic.split('/')
    camera_id = topic_parts[-1] if len(topic_parts) >= 2 else "unknown"

    # Decode RGB numpy array from bytes
    frame_rgb = np.frombuffer(msg.payload, dtype=np.uint8).reshape((IMG_H, IMG_W, IMG_C))
    
    # Convert to PIL for transforms (or apply directly)
    pil_img = Image.fromarray(frame_rgb)
    input_tensor = preprocess(pil_img).unsqueeze(0).to(device)
    
    # Run Inference
    t0 = time.time()
    with torch.no_grad():
        output = model(input_tensor)
        probs = F.softmax(output, dim=1)
        pred_class_idx = torch.argmax(probs, dim=1).item()
        confidence = probs[0][pred_class_idx].item()
    
    elapsed_ms = (time.time() - t0) * 1000.0
    detection_class = class_names[pred_class_idx]
    
    prefix = "🔥 " if detection_class == "fire" else "🌲 "
    print(f"[{camera_id}] {prefix}{detection_class.upper()} conf={confidence:.3f} (latency={elapsed_ms:.1f}ms)")

def main():
    print("="*50)
    print("Local Edge Test: Python PyTorch Inference Engine")
    print("="*50)
    
    load_model()

    client = mqtt.Client(CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
    except Exception as e:
        print(f"[ERROR] Failed to connect to broker: {e}")
        return

    # Blocking loop to continuously process frames arriving on MQTT
    client.loop_forever()

if __name__ == "__main__":
    main()
