import os
import time
import glob
import cv2
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

# Env config
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
VIDEO_DIR = os.getenv("VIDEO_DIR", "..") # Directory containing mp4 videos
TOPIC = "frames/test_cam_1"
FPS = int(os.getenv("FPS", "2")) # Target frames per second to extract

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"Connected to MQTT Broker ({MQTT_BROKER}:{MQTT_PORT})")
    else:
        print(f"Failed to connect, return code {rc}")

def main():
    print(f"--- Starting local folder frame extractor ---")
    print(f"Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Source Dir: {VIDEO_DIR}")
    print(f"Topic:  {TOPIC}")
    
    # Find all mp4 files in the directory
    video_files = glob.glob(os.path.join(VIDEO_DIR, "*.mp4"))
    if not video_files:
        print(f"[ERROR] No .mp4 files found in {VIDEO_DIR}")
        return
        
    print(f"Found {len(video_files)} video files:")
    for vf in video_files:
        print(f"  - {os.path.basename(vf)}")
    
    client = mqtt.Client(CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(f"[ERROR] Could not connect to MQTT broker: {e}")
        return

    client.loop_start()
    delay = 1.0 / FPS
    
    try:
        while True:
            for video_path in video_files:
                print(f"Opening video: {os.path.basename(video_path)}")
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    print(f"[WARNING] Could not open {video_path}, skipping...")
                    continue
                
                while True:
                    start_t = time.time()
                    ret, frame = cap.read()
                    if not ret:
                        print(f"Finished playing {os.path.basename(video_path)}")
                        break # Move to next video
                        
                    # Convert to RGB & resize to 224x224 (model expected input size)
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    resized = cv2.resize(rgb_frame, (224, 224))
                    
                    # Publish raw bytes
                    payload = resized.tobytes()
                    client.publish(TOPIC, payload, qos=0)
                    print(f"Published frame ({len(payload)} bytes) from {os.path.basename(video_path)} to {TOPIC}")
                    
                    # Maintain target FPS
                    elapsed = time.time() - start_t
                    sleep_time = delay - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                
                cap.release()
            
            print("Finished all videos in directory. Restarting loop...")

    except KeyboardInterrupt:
        print("Stopping extractor...")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
