"""
MQTT-to-inference bridge (sidecar).

Subscribes to MQTT frames/#, forwards each frame to the C++ backend
(localhost:8080/predict), and exports Prometheus metrics with location labels.

Prometheus metrics (port 9090):
  fire_detection_total{location, result}       — counter
  fire_detection_confidence{location, lat, lon} — gauge (latest confidence)
  fire_detection_latency_seconds{location}      — histogram
"""

import json
import os
import time
import threading
import requests
import paho.mqtt.client as mqtt
from prometheus_client import (
    Counter, Gauge, Histogram, start_http_server
)

MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker.fire-detection.svc")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080/predict")
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9090"))

detect_total = Counter(
    "fire_detection_total",
    "Total fire detection inferences",
    ["location", "result"],
)
detect_confidence = Gauge(
    "fire_detection_confidence",
    "Latest detection confidence",
    ["location", "lat", "lon"],
)
detect_latency = Histogram(
    "fire_detection_latency_seconds",
    "Inference latency",
    ["location"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

location_meta: dict[str, dict] = {}


def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT (rc={rc})")
    client.subscribe("frames/#")


def on_message(client, userdata, msg):
    topic = msg.topic

    if topic.endswith("/meta"):
        loc_id = topic.split("/")[1]
        try:
            location_meta[loc_id] = json.loads(msg.payload)
        except Exception:
            pass
        return

    loc_id = topic.split("/")[1] if "/" in topic else "unknown"
    meta = location_meta.get(loc_id, {})
    lat = str(meta.get("lat", "0"))
    lon = str(meta.get("lon", "0"))

    payload = msg.payload
    if len(payload) != 150528:
        return

    t0 = time.monotonic()
    try:
        resp = requests.post(
            BACKEND_URL,
            data=payload,
            headers={"Content-Type": "application/octet-stream"},
            timeout=5,
        )
        result = resp.json()
    except Exception as e:
        print(f"[{loc_id}] Inference error: {e}")
        return

    elapsed = time.monotonic() - t0
    cls = result.get("class", "unknown")
    conf = result.get("confidence", 0.0)

    detect_total.labels(location=loc_id, result=cls).inc()
    detect_confidence.labels(location=loc_id, lat=lat, lon=lon).set(conf)
    detect_latency.labels(location=loc_id).observe(elapsed)

    if cls == "fire":
        print(f"[{loc_id}] FIRE detected (conf={conf:.3f}, latency={elapsed:.3f}s)")


def main():
    start_http_server(METRICS_PORT)
    print(f"Prometheus metrics on :{METRICS_PORT}")

    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
