# exporter/mqtt_handler.py
import json
import base64
import os
import paho.mqtt.client as mqtt
from datetime import datetime
from typing import Callable, Optional
import threading
import random
import time

from metrics import FireAlert, get_metrics
from notification import NotificationService
from fire_detector import FireDetector, DetectionResult

class MQTTHandler:
    def __init__(
        self,
        broker: str = "localhost",
        port: int = 1883,
        images_dir: str = "./images",
        image_base_url: str = "http://localhost:8080/images",
        simulate_fire: bool = False,
        simulate_smoke: bool = False,
        model_path: Optional[str] = None,
        alert_cooldown_seconds: int = 300  # 5 minutes default
    ):
        self.broker = broker
        self.port = port
        self.images_dir = images_dir
        self.image_base_url = image_base_url
        self.alert_cooldown_seconds = alert_cooldown_seconds

        self.client = mqtt.Client(client_id="fire_exporter")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self.metrics = get_metrics()
        self.notification = NotificationService()

        # Initialize fire detector
        self.fire_detector = FireDetector(
            simulate_fire=simulate_fire,
            simulate_smoke=simulate_smoke,
            model_path=model_path
        )

        self.connected = False

        # Ensure images directory exists
        os.makedirs(images_dir, exist_ok=True)

        # Scan history for debugging (saves all scanned images)
        self.scans_dir = os.path.join(images_dir, "scans")
        self.scan_history_file = os.path.join(images_dir, "scan_history.json")
        self.scan_history = []
        os.makedirs(self.scans_dir, exist_ok=True)
        self._load_scan_history()

        # Alert cooldown tracking: {(device_id, location_name): {"alert_id": ..., "timestamp": ..., "confidence": ...}}
        self.active_cooldowns = {}

    def _load_scan_history(self):
        """Load existing scan history from file"""
        try:
            if os.path.exists(self.scan_history_file):
                with open(self.scan_history_file, 'r') as f:
                    self.scan_history = json.load(f)
                print(f"[SCAN] Loaded {len(self.scan_history)} scan records")
        except Exception as e:
            print(f"[SCAN] Failed to load scan history: {e}")
            self.scan_history = []

    def _save_scan_history(self):
        """Save scan history to file"""
        try:
            with open(self.scan_history_file, 'w') as f:
                json.dump(self.scan_history, f, indent=2)
        except Exception as e:
            print(f"[SCAN] Failed to save scan history: {e}")

    def _add_scan_record(self, scan_id: str, device_id: str, timestamp: str,
                         location: dict, detected: bool, detection_class: str,
                         confidence: float, image_filename: str):
        """Add a scan record to history"""
        record = {
            "scan_id": scan_id,
            "device_id": device_id,
            "timestamp": timestamp,
            "location": location,
            "detected": detected,
            "detection_class": detection_class,
            "confidence": confidence,
            "image_filename": image_filename,
            "image_url": f"{self.image_base_url}/scans/{image_filename}"
        }
        self.scan_history.append(record)

        # Keep only last 1000 records to prevent file from growing too large
        if len(self.scan_history) > 1000:
            self.scan_history = self.scan_history[-1000:]

        self._save_scan_history()
        return record

    def get_scan_history(self, limit: int = 100, detected_only: bool = False):
        """Get scan history records"""
        records = self.scan_history
        if detected_only:
            records = [r for r in records if r.get('detected')]
        return records[-limit:]

    def _get_cooldown_key(self, device_id: str, location_name: str) -> tuple:
        """Generate cooldown key from device_id and location"""
        return (device_id, location_name)

    def _is_in_cooldown(self, device_id: str, location_name: str) -> tuple:
        """
        Check if an alert for this device+location is in cooldown period.
        Returns (is_in_cooldown, existing_alert_info)
        """
        key = self._get_cooldown_key(device_id, location_name)
        if key not in self.active_cooldowns:
            return False, None

        cooldown_info = self.active_cooldowns[key]
        elapsed = time.time() - cooldown_info['timestamp']

        if elapsed >= self.alert_cooldown_seconds:
            # Cooldown expired, remove it
            del self.active_cooldowns[key]
            return False, None

        return True, cooldown_info

    def _set_cooldown(self, device_id: str, location_name: str, alert_id: str, confidence: float):
        """Set cooldown for device+location"""
        key = self._get_cooldown_key(device_id, location_name)
        self.active_cooldowns[key] = {
            'alert_id': alert_id,
            'timestamp': time.time(),
            'confidence': confidence
        }

    def _update_cooldown_confidence(self, device_id: str, location_name: str,
                                     new_confidence: float, new_image_url: str = None):
        """Update confidence of existing cooldown alert if new confidence is higher"""
        key = self._get_cooldown_key(device_id, location_name)
        if key in self.active_cooldowns:
            old_confidence = self.active_cooldowns[key]['confidence']
            if new_confidence > old_confidence:
                self.active_cooldowns[key]['confidence'] = new_confidence
                alert_id = self.active_cooldowns[key]['alert_id']

                # Update the alert in metrics
                self.metrics.update_alert_confidence(alert_id, new_confidence, new_image_url)
                print(f"[COOLDOWN] Updated alert {alert_id} confidence: {old_confidence:.2f} -> {new_confidence:.2f}")
                return True
        return False

    def _increment_alert_frames(self, device_id: str, location_name: str):
        """Increment frame count for active alert so Grafana pinpoint grows"""
        key = self._get_cooldown_key(device_id, location_name)
        if key in self.active_cooldowns:
            alert_id = self.active_cooldowns[key]['alert_id']
            if alert_id in self.metrics.active_alerts:
                alert = self.metrics.active_alerts[alert_id]
                # Increment and force gauge update
                alert.fire_frames_count += 1
                self.metrics._update_metrics(alert)
                return True
        return False

    def connect(self):
        """Connect to MQTT broker"""
        while True:
            try:
                self.client.connect(self.broker, self.port, keepalive=60)
                self.client.loop_start()
                print(f"Connecting to MQTT broker: {self.broker}:{self.port}")
                break
            except Exception as e:
                print(f"Failed to connect to MQTT: {e}. Retrying in 5 seconds...")
                time.sleep(5)

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
            client.subscribe("wildfire/resolved")
            client.subscribe("wildfire/devices/status")
            client.subscribe("wildfire/images")  # New: device sends image for AI detection
            print("Subscribed to wildfire/alerts, wildfire/heartbeat, wildfire/resolved, wildfire/devices/status, wildfire/images")
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
            elif topic == "wildfire/resolved":
                self._handle_resolved(payload)
            elif topic == "wildfire/devices/status":
                self._handle_device_status(payload)
            elif topic == "wildfire/images":
                self._handle_image_detection(payload)

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

        # Check cooldown - prevent alert spam from same device+location
        in_cooldown, cooldown_info = self._is_in_cooldown(device_id, location_name)

        # Save image if included
        image_url = ""
        filepath = None
        image_base64 = payload.get('image_base64')
        if image_base64:
            print(f"Received image_base64: {len(image_base64)} bytes")
            try:
                image_data = base64.b64decode(image_base64)
                
                # If in cooldown and new confidence is not higher, skip saving to reduce disk I/O
                if in_cooldown and confidence <= cooldown_info['confidence']:
                    pass
                else:
                    filename = f"temp_{int(time.time())}_{random.randint(100, 999)}.jpg" if in_cooldown else f"{alert_id}.jpg"
                    filepath = os.path.join(self.images_dir, filename)

                    # Ensure directory exists
                    os.makedirs(self.images_dir, exist_ok=True)

                    with open(filepath, 'wb') as f:
                        f.write(image_data)

                    image_url = f"{self.image_base_url}/{filename}"
                    print(f"Saved image: {filepath}, URL: {image_url}")

            except Exception as e:
                print(f"Failed to save image: {e}")
                filepath = None
        else:
            print(f"No image_base64 in payload for alert {alert_id}")

        if in_cooldown:
            print(f"[COOLDOWN] Alert for {device_id}@{location_name} is in cooldown (alert: {cooldown_info['alert_id']})")
            if confidence > cooldown_info['confidence']:
                self._update_cooldown_confidence(device_id, location_name, confidence, image_url)
            else:
                print(f"[COOLDOWN] Skipping - new confidence ({confidence:.2f}) <= existing ({cooldown_info['confidence']:.2f})")
            return

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

        # Set cooldown for this device+location
        self._set_cooldown(device_id, location_name, alert_id, confidence)

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

    def _handle_device_status(self, payload: dict):
        """Process device status update from wildfire/devices/status topic"""
        device_id = payload.get('device_id', '')
        status = payload.get('status', 'offline')
        is_online = status.lower() == 'online'

        # Get location from payload or use defaults based on device_id
        location_data = payload.get('location', {})
        if location_data:
            latitude = location_data.get('lat', 0)
            longitude = location_data.get('lon', 0)
            location_name = location_data.get('name', 'Unknown')
        else:
            # Use device's last known location or default Vietnam coordinates
            existing = self.metrics.device_status.get(device_id, {})
            latitude = existing.get('latitude', 21.0285)  # Hanoi default
            longitude = existing.get('longitude', 105.8542)
            location_name = existing.get('location', f'Device {device_id}')

        # Extract additional device info
        battery = payload.get('battery', 0)
        temperature = payload.get('temperature', 0)
        uptime = payload.get('uptime', 0)

        print(f"[DEVICE STATUS] {device_id}: {status}")
        print(f"  - Battery: {battery}%")
        print(f"  - Temperature: {temperature}°C")
        print(f"  - Uptime: {uptime}s")

        self.metrics.update_device_status(
            device_id=device_id,
            latitude=latitude,
            longitude=longitude,
            location=location_name,
            is_online=is_online,
            battery=battery,
            temperature=temperature,
            uptime=uptime
        )

    def _handle_image_detection(self, payload: dict):
        """
        Process image from device and run AI fire detection.

        This is the new flow for edge devices:
        1. Device captures image and sends to this topic
        2. Exporter runs AI model to detect fire/smoke
        3. Save ALL images to scans/ directory for debugging
        4. If detected, create alert and update metrics

        Payload format:
        {
            "device_id": "edge_device_001",
            "timestamp": "2024-01-15T10:30:00Z",
            "location": {"lat": 21.0285, "lon": 105.8542, "name": "Location name"},
            "image_base64": "base64_encoded_image_data"
        }
        """
        device_id = payload.get('device_id', 'unknown')
        timestamp = payload.get('timestamp', datetime.now().isoformat())
        location_data = payload.get('location', {})
        image_base64 = payload.get('image_base64')

        print(f"[IMAGE] Received image from device: {device_id}")

        if not image_base64:
            print(f"[IMAGE] No image data in payload, skipping")
            return

        # Decode image
        try:
            image_data = base64.b64decode(image_base64)
            print(f"[IMAGE] Decoded image: {len(image_data)} bytes")
        except Exception as e:
            print(f"[IMAGE] Failed to decode image: {e}")
            return

        # Generate scan ID for ALL images
        scan_id = f"scan_{int(time.time())}_{random.randint(100, 999)}"

        # Run AI detection
        result = self.fire_detector.detect(image_data)
        print(f"[IMAGE] Detection result: detected={result.detected}, class={result.detection_class}, confidence={result.confidence:.2f}")

        # Save ALL images to scans/ directory for debugging
        scan_filename = f"{scan_id}.jpg"
        scan_filepath = os.path.join(self.scans_dir, scan_filename)
        try:
            with open(scan_filepath, 'wb') as f:
                f.write(image_data)
            print(f"[SCAN] Saved scan image: {scan_filepath}")
        except Exception as e:
            print(f"[SCAN] Failed to save scan image: {e}")
            scan_filename = ""

        # Add to scan history (regardless of detection result)
        self._add_scan_record(
            scan_id=scan_id,
            device_id=device_id,
            timestamp=timestamp,
            location=location_data,
            detected=result.detected,
            detection_class=result.detection_class,
            confidence=result.confidence,
            image_filename=scan_filename
        )

        if not result.detected:
            print(f"[IMAGE] No fire/smoke detected, skipping alert creation")
            return

        # Fire/smoke detected
        latitude = location_data.get('lat', 0)
        longitude = location_data.get('lon', 0)
        location_name = location_data.get('name', 'Unknown')

        # Check cooldown - prevent alert spam from same device+location
        in_cooldown, cooldown_info = self._is_in_cooldown(device_id, location_name)

        if in_cooldown:
            # In cooldown period - only update if confidence is higher
            print(f"[COOLDOWN] Alert for {device_id}@{location_name} is in cooldown (alert: {cooldown_info['alert_id']})")

            # Save image for potential update
            temp_image_url = ""
            try:
                temp_filename = f"temp_{int(time.time())}_{random.randint(100, 999)}.jpg"
                temp_filepath = os.path.join(self.images_dir, temp_filename)
                with open(temp_filepath, 'wb') as f:
                    f.write(image_data)
                temp_image_url = f"{self.image_base_url}/{temp_filename}"
            except Exception as e:
                print(f"[IMAGE] Failed to save temp image: {e}")

            if result.confidence > cooldown_info['confidence']:
                self._update_cooldown_confidence(device_id, location_name, result.confidence, temp_image_url)
            else:
                print(f"[COOLDOWN] Skipping - new confidence ({result.confidence:.2f}) <= existing ({cooldown_info['confidence']:.2f})")
            return

        # Not in cooldown - create new alert
        alert_id = f"alert_{int(time.time())}_{random.randint(100, 999)}"

        # Save image to alerts directory (for Grafana display)
        image_url = ""
        filepath = None
        try:
            filename = f"{alert_id}.jpg"
            filepath = os.path.join(self.images_dir, filename)
            os.makedirs(self.images_dir, exist_ok=True)

            with open(filepath, 'wb') as f:
                f.write(image_data)

            image_url = f"{self.image_base_url}/{filename}"
            print(f"[IMAGE] Saved alert image: {filepath}")
        except Exception as e:
            print(f"[IMAGE] Failed to save alert image: {e}")

        # Create alert
        alert = FireAlert(
            alert_id=alert_id,
            device_id=device_id,
            latitude=latitude,
            longitude=longitude,
            location=location_name,
            confidence=result.confidence,
            detection_class=result.detection_class,
            detected_at=timestamp,
            image_url=image_url
        )

        # Add to metrics
        self.metrics.add_alert(alert)

        # Set cooldown for this device+location
        self._set_cooldown(device_id, location_name, alert_id, result.confidence)
        print(f"[IMAGE] Created alert: {alert_id} ({result.detection_class} at {result.confidence*100:.1f}%) - cooldown set for {self.alert_cooldown_seconds}s")

        # Send notification
        threading.Thread(
            target=self._send_notification,
            args=(alert, filepath),
            daemon=True
        ).start()

    def _handle_resolved(self, payload: dict):
        """Process alert resolution"""
        alert_id = payload.get('alert_id', '')
        resolution_type = payload.get('resolution_type', 'resolved')
        resolved_by = payload.get('resolved_by', 'unknown')
        notes = payload.get('notes', '')

        print(f"Received resolution for alert: {alert_id}")
        print(f"  - Type: {resolution_type}")
        print(f"  - By: {resolved_by}")
        if notes:
            print(f"  - Notes: {notes}")

        # Remove alert from metrics (this will stop Alertmanager reminders)
        self.metrics.remove_alert(alert_id, resolution_type, resolved_by)

        # Send resolution notification
        threading.Thread(
            target=self._send_resolution_notification,
            args=(alert_id, resolution_type, resolved_by, notes),
            daemon=True
        ).start()

    def _send_notification(self, alert: FireAlert, image_path: Optional[str]):
        """Send notification in background thread"""
        try:
            self.notification.send_alert(alert, image_path)
        except Exception as e:
            print(f"Failed to send notification: {e}")

    def _send_resolution_notification(self, alert_id: str, resolution_type: str,
                                       resolved_by: str, notes: str):
        """Send resolution notification via Telegram"""
        try:
            self.notification.send_resolution(alert_id, resolution_type, resolved_by, notes)
        except Exception as e:
            print(f"Failed to send resolution notification: {e}")