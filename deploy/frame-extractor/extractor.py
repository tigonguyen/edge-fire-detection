"""
Simulates camera feeds by extracting frames from video files and
publishing them to MQTT with location metadata.

Each video is mapped to a GPS location (simulating a camera on a map).
Frames are resized to 224x224 RGB and published as raw bytes.

MQTT topic format: frames/<location_id>
MQTT payload: raw 224x224x3 bytes (150528 B)
MQTT user-property headers (v5) or retained JSON on frames/<location_id>/meta
"""

import json
import os
import time
import cv2
import numpy as np
import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker.fire-detection.svc")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
FRAME_INTERVAL = float(os.environ.get("FRAME_INTERVAL", "2.0"))
SOURCES_JSON = os.environ.get("SOURCES_JSON", "/config/sources.json")
VIDEO_DIR = os.environ.get("VIDEO_DIR", "/videos")

IMG_SIZE = 224


def load_sources(path):
    with open(path) as f:
        return json.load(f)


def extract_and_publish(client, source):
    loc_id = source["id"]
    lat = source["lat"]
    lon = source["lon"]
    video_path = os.path.join(VIDEO_DIR, source["file"])

    meta = json.dumps({"id": loc_id, "lat": lat, "lon": lon, "file": source["file"]})
    client.publish(f"frames/{loc_id}/meta", meta, retain=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[{loc_id}] Cannot open {video_path}")
        return

    print(f"[{loc_id}] Streaming from {video_path} (lat={lat}, lon={lon})")
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (IMG_SIZE, IMG_SIZE))

        payload = rgb.tobytes()
        client.publish(f"frames/{loc_id}", payload)
        time.sleep(FRAME_INTERVAL)

    cap.release()


def main():
    sources = load_sources(SOURCES_JSON)
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    print(f"Connected to MQTT {MQTT_HOST}:{MQTT_PORT}")
    print(f"Sources: {len(sources)}, interval: {FRAME_INTERVAL}s")

    import threading
    threads = []
    for src in sources:
        t = threading.Thread(target=extract_and_publish, args=(client, src), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
