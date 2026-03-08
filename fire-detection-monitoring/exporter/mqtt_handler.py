# exporter/mqtt_handler.py
import json
import base64
import os
import paho.mqtt.client as mqtt
from datetime import datetime
from typing import Callable, Optional
import threading

from metrics import FireAlert, get_metrics
from notification import NotificationService

class MQTTHandler:
    def __init__(
        self,
        broker: str = "localhost",
        port: int = 1883,
        images_dir: str = "./images",
        image_base_url: str = "http://localhost:8080/images"
    ):
        self.broker = broker
        self.port = port
        self.images_dir = images_dir
        self.image_base_url = image_base_url

        self.client = mqtt.Client(client_id="fire_exporter")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self.metrics = get_metrics()
        self.notification = NotificationService()

        self.connected = False

        # Ensure images directory exists
        os.makedirs(images_dir, exist_ok=True)

    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            print(f"Connecting to MQTT broker: {self.broker}:{self.port}")
        except Exception as e:
            print(f"Failed to connect to MQTT: {e}")
            raise

    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            print("Connected to MQTT broker")

            # Subscribe to topics
            client.subscribe("wildfire/alerts")
            client.subscribe("wildfire/heartbeat")
            print("Subscribed to wildfire/alerts and wildfire/heartbeat")
        else:
            print(f"Failed to connect, return code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        print(f"Disconnected from MQTT broker (rc={rc})")

        # Auto reconnect
        if rc != 0:
            print("Attempting to reconnect...")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode())

            if topic == "wildfire/alerts":
                self._handle_alert(payload)
            elif topic == "wildfire/heartbeat":
                self._handle_heartbeat(payload)

        except json.JSONDecodeError as e:
            print(f"Invalid JSON in message: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")

    def _handle_alert(self, payload: dict):
        """Process fire detection alert"""
        print(f"Received alert: {payload.get('alert_id')}")

        # Extract data
        alert_id = payload.get('alert_id', '')
        device_id = payload.get('device_id', '')
        location_data = payload.get('location', {})
        timestamp = payload.get('timestamp', datetime.now().isoformat())

        latitude = location_data.get('lat', 0)
        longitude = location_data.get('lon', 0)
        location_name = location_data.get('name', 'Unknown')

        confidence = payload.get('confidence_max', 0)
        detections = payload.get('detections', [])

        # Get detection class
        detection_class = 'fire'
        if detections:
            detection_class = detections[0].get('class', 'fire')

        # Save image if included
        image_url = ""
        filepath = None
        if payload.get('image_base64'):
            try:
                image_data = base64.b64decode(payload['image_base64'])
                filename = f"{alert_id}.jpg"
                filepath = os.path.join(self.images_dir, filename)

                with open(filepath, 'wb') as f:
                    f.write(image_data)

                image_url = f"{self.image_base_url}/{filename}"
                print(f"Saved image: {filepath}")

            except Exception as e:
                print(f"Failed to save image: {e}")
                filepath = None

        # Create FireAlert object
        alert = FireAlert(
            alert_id=alert_id,
            device_id=device_id,
            latitude=latitude,
            longitude=longitude,
            location=location_name,
            confidence=confidence,
            detection_class=detection_class,
            detected_at=timestamp,
            image_url=image_url
        )

        # Add to metrics
        self.metrics.add_alert(alert)

        # Send notification
        threading.Thread(
            target=self._send_notification,
            args=(alert, filepath),
            daemon=True
        ).start()

    def _handle_heartbeat(self, payload: dict):
        """Process device heartbeat"""
        device_id = payload.get('device_id', '')
        location_data = payload.get('location', {})

        latitude = location_data.get('lat', 0)
        longitude = location_data.get('lon', 0)
        location_name = location_data.get('name', 'Unknown')

        self.metrics.update_device_status(
            device_id=device_id,
            latitude=latitude,
            longitude=longitude,
            location=location_name,
            is_online=True
        )

    def _send_notification(self, alert: FireAlert, image_path: Optional[str]):
        """Send notification in background thread"""
        try:
            self.notification.send_alert(alert, image_path)
        except Exception as e:
            print(f"Failed to send notification: {e}")