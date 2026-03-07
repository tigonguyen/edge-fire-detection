"""
Fire detection inference service for edge deployment.

Single process that:
  1. Subscribes to MQTT topic frames/# to receive video frames
  2. Runs ONNX Runtime inference (EfficientNet-Lite0)
  3. Exports Prometheus metrics with location labels (lat/lon)

Prometheus metrics (port METRICS_PORT):
  fire_detection_total{location, result}            — counter
  fire_detection_confidence{location, lat, lon}      — gauge
  fire_detection_latency_seconds{location}           — histogram
"""

import json
import os
import time
import numpy as np
import onnxruntime as ort
import paho.mqtt.client as mqtt
from prometheus_client import Counter, Gauge, Histogram, start_http_server

MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker.fire-detection.svc")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MODEL_PATH = os.environ.get("MODEL_PATH", "/model/fire_detection.onnx")
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9090"))
CLASS_NAMES = os.environ.get("CLASS_NAMES", "fire,normal").split(",")

IMG_SIZE = 224
FRAME_BYTES = IMG_SIZE * IMG_SIZE * 3  # 150528

# ImageNet normalization (same as training pipeline)
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# ── Prometheus metrics ────────────────────────────────────────────────

detect_total = Counter(
    "fire_detection_total",
    "Total fire detection inferences",
    ["location", "result"],
)
detect_confidence = Gauge(
    "fire_detection_confidence",
    "Latest detection confidence for each location",
    ["location", "lat", "lon"],
)
detect_latency = Histogram(
    "fire_detection_latency_seconds",
    "ONNX inference latency in seconds",
    ["location"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# ── Global state ──────────────────────────────────────────────────────

location_meta: dict[str, dict] = {}
session: ort.InferenceSession = None
input_name: str = None


def load_model():
    global session, input_name
    opts = ort.SessionOptions()
    opts.inter_op_num_threads = 2
    opts.intra_op_num_threads = 2
    session = ort.InferenceSession(MODEL_PATH, sess_options=opts)
    input_name = session.get_inputs()[0].name
    print(f"Model loaded: {MODEL_PATH} | input: {input_name}")


def preprocess(raw_bytes: bytes) -> np.ndarray:
    """Convert raw 224x224x3 uint8 bytes to NCHW float32 tensor."""
    img = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(IMG_SIZE, IMG_SIZE, 3)
    img = img.astype(np.float32) / 255.0
    img = (img - MEAN) / STD
    # HWC → CHW → NCHW
    return np.expand_dims(img.transpose(2, 0, 1), axis=0)


def softmax(logits):
    e = np.exp(logits - np.max(logits))
    return e / e.sum()


def infer(frame_bytes: bytes) -> tuple[str, float]:
    """Run inference, return (class_name, confidence)."""
    tensor = preprocess(frame_bytes)
    logits = session.run(None, {input_name: tensor})[0][0]
    probs = softmax(logits)
    idx = int(np.argmax(probs))
    return CLASS_NAMES[idx], float(probs[idx])


# ── MQTT callbacks ────────────────────────────────────────────────────

def on_connect(client, userdata, flags, rc):
    print(f"MQTT connected (rc={rc})")
    client.subscribe("frames/#")


def on_message(client, userdata, msg):
    topic = msg.topic

    # Metadata messages (retained)
    if topic.endswith("/meta"):
        loc_id = topic.split("/")[1]
        try:
            location_meta[loc_id] = json.loads(msg.payload)
        except Exception:
            pass
        return

    # Frame messages
    if len(msg.payload) != FRAME_BYTES:
        return

    loc_id = topic.split("/")[1] if "/" in topic else "unknown"
    meta = location_meta.get(loc_id, {})
    lat = str(meta.get("lat", "0"))
    lon = str(meta.get("lon", "0"))

    t0 = time.monotonic()
    cls, conf = infer(msg.payload)
    elapsed = time.monotonic() - t0

    detect_total.labels(location=loc_id, result=cls).inc()
    detect_confidence.labels(location=loc_id, lat=lat, lon=lon).set(conf)
    detect_latency.labels(location=loc_id).observe(elapsed)

    if cls == "fire":
        print(f"[{loc_id}] FIRE  conf={conf:.3f}  latency={elapsed:.3f}s")


# ── Main ──────────────────────────────────────────────────────────────

def main():
    load_model()

    start_http_server(METRICS_PORT)
    print(f"Prometheus metrics on :{METRICS_PORT}")

    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    print(f"Subscribing to MQTT {MQTT_HOST}:{MQTT_PORT}")
    client.loop_forever()


if __name__ == "__main__":
    main()
