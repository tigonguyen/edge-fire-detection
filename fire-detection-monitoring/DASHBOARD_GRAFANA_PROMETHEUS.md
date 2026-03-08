# Hướng Dẫn Xây Dựng Dashboard với Grafana Geomap & Prometheus

## Mục Lục

1. [Tổng Quan Hệ Thống](#1-tổng-quan-hệ-thống)
2. [Cài Đặt Môi Trường](#2-cài-đặt-môi-trường)
3. [Prometheus Metrics Format](#3-prometheus-metrics-format)
4. [Backend Exporter](#4-backend-exporter)
5. [Cấu Hình Prometheus](#5-cấu-hình-prometheus)
6. [Cấu Hình Grafana Geomap](#6-cấu-hình-grafana-geomap)
7. [Push Notification](#7-push-notification)
8. [Alertmanager Integration](#8-alertmanager-integration)
9. [Complete Docker Setup](#9-complete-docker-setup)
10. [Testing & Verification](#10-testing--verification)

---

## 1. Tổng Quan Hệ Thống

### 1.1 Kiến Trúc

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EDGE DEVICES                                   │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│   │ Edge Device 1│    │ Edge Device 2│    │ Edge Device N│                  │
│   │  (Camera)    │    │  (Camera)    │    │  (Camera)    │                  │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                  │
└──────────┼───────────────────┼───────────────────┼──────────────────────────┘
           │                   │                   │
           │              MQTT Protocol            │
           └───────────────────┼───────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GROUND STATION                                    │
│                                                                             │
│   ┌──────────────┐         ┌──────────────────────────────────────────┐     │
│   │ MQTT Broker  │────────▶│         Fire Detection Exporter          │     │
│   │ (Mosquitto)  │         │  - Nhận alerts từ MQTT                   │     │
│   └──────────────┘         │  - Expose metrics cho Prometheus         │     │
│                            │  - Lưu images                            │     │
│                            │  - Gửi push notification                 │     │
│                            └─────────────┬────────────────────────────┘     │
│                                          │                                  │
│                                          │ :8000/metrics                    │
│                                          ▼                                  │
│   ┌──────────────────────────────────────────────────────────────────┐      │
│   │                        PROMETHEUS                                │      │
│   │  - Scrape metrics từ Exporter                                    │      │
│   │  - Lưu trữ time-series data                                      │      │
│   │  - Query với PromQL                                              │      │
│   └─────────────┬─────────────────────────────────┬──────────────────┘      │
│                 │                                 │                         │
│                 ▼                                 ▼                         │
│   ┌─────────────────────────┐       ┌─────────────────────────┐             │
│   │        GRAFANA          │       │      ALERTMANAGER       │             │
│   │  - Geomap visualization │       │  - Telegram             │             │
│   │  - Alert history        │       │  - Email                │             │
│   │  - Statistics           │       │  - Webhook              │             │
│   └─────────────────────────┘       └─────────────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow

```
Edge Device ──MQTT──▶ Exporter ──metrics──▶ Prometheus ──query──▶ Grafana Geomap
                         │
                         └──notification──▶ Telegram/Email
```

### 1.3 Tính Năng


| Feature       | Mô tả                                      |
| ------------- | ------------------------------------------ |
| **Geomap**    | Hiển thị vị trí phát hiện cháy trên bản đồ |
| **Metrics**   | Confidence score, timestamp, device info   |
| **Images**    | Link ảnh chụp trong annotation             |
| **Real-time** | Cập nhật tự động qua Prometheus scrape     |
| **Alerting**  | Push notification qua Alertmanager         |


---

## 2. Cài Đặt Môi Trường

### 2.1 Cấu Trúc Project

```
fire-detection-monitoring/
├── docker-compose.yml
├── exporter/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── metrics.py
│   ├── mqtt_handler.py
│   └── notification.py
├── prometheus/
│   ├── prometheus.yml
│   └── alerts.yml
├── alertmanager/
│   └── alertmanager.yml
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── prometheus.yml
│   │   └── dashboards/
│   │       ├── dashboard.yml
│   │       └── fire-detection.json
│   └── grafana.ini
├── mosquitto/
│   └── mosquitto.conf
├── images/                    # Lưu ảnh từ alerts
└── .env
```

### 2.2 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  # MQTT Broker
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: mosquitto
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf
      - mosquitto_data:/mosquitto/data
      - mosquitto_log:/mosquitto/log
    restart: unless-stopped

  # Fire Detection Exporter (Custom metrics exporter)
  exporter:
    build: ./exporter
    container_name: fire_exporter
    ports:
      - "8000:8000"
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - IMAGES_DIR=/app/images
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
    volumes:
      - ./images:/app/images
    depends_on:
      - mosquitto
    restart: unless-stopped

  # Prometheus
  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus/alerts.yml:/etc/prometheus/alerts.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.enable-lifecycle'
      - '--storage.tsdb.retention.time=30d'
    depends_on:
      - exporter
    restart: unless-stopped

  # Alertmanager
  alertmanager:
    image: prom/alertmanager:v0.26.0
    container_name: alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
    restart: unless-stopped

  # Grafana
  grafana:
    image: grafana/grafana:10.2.2
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_INSTALL_PLUGINS=grafana-worldmap-panel
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/grafana.ini:/etc/grafana/grafana.ini
      - grafana_data:/var/lib/grafana
      - ./images:/var/lib/grafana/images:ro
    depends_on:
      - prometheus
    restart: unless-stopped

  # Nginx để serve images
  nginx:
    image: nginx:alpine
    container_name: nginx_images
    ports:
      - "8080:80"
    volumes:
      - ./images:/usr/share/nginx/html/images:ro
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    restart: unless-stopped

volumes:
  mosquitto_data:
  mosquitto_log:
  prometheus_data:
  grafana_data:
```

---

## 3. Prometheus Metrics Format

### 3.1 Metrics Cần Thiết Cho Geomap

> **QUAN TRỌNG**: Grafana Geomap cần các trường data sau từ Prometheus:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROMETHEUS METRICS CHO GEOMAP                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. METRIC VALUE (bắt buộc)                                                 │
│     - Giá trị số để hiển thị (confidence, count, etc.)                      │
│                                                                             │
│  2. LABELS (bắt buộc cho vị trí)                                            │
│     - latitude  : vĩ độ (số thực, ví dụ: 21.0285)                           │
│     - longitude : kinh độ (số thực, ví dụ: 105.8542)                        │
│                                                                             │
│  3. LABELS (tùy chọn - hiển thị trong tooltip/popup)                        │
│     - device_id    : ID thiết bị                                            │
│     - location     : Tên vị trí                                             │
│     - alert_id     : ID cảnh báo                                            │
│     - image_url    : URL ảnh chụp                                           │
│     - detected_at  : Timestamp phát hiện                                    │
│     - class        : Loại phát hiện (fire/smoke)                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Định Nghĩa Metrics

```python
# Các metrics cần expose cho Prometheus

# 1. Fire Alert với vị trí (GAUGE - cho Geomap)
fire_alert_info{
    alert_id="abc123",
    device_id="edge_001",
    latitude="21.0285",
    longitude="105.8542",
    location="Khu rừng A",
    confidence="0.92",
    class="fire",
    detected_at="2024-01-15T10:30:00Z",
    image_url="http://localhost:8080/images/abc123.jpg"
} 0.92

# 2. Tổng số alerts theo device (COUNTER)
fire_alerts_total{device_id="edge_001", location="Khu rừng A"} 15

# 3. Device status (GAUGE)
device_status{
    device_id="edge_001",
    latitude="21.0285",
    longitude="105.8542",
    location="Khu rừng A"
} 1  # 1 = online, 0 = offline

# 4. Latest confidence per location (GAUGE - cho Geomap)
fire_confidence_latest{
    device_id="edge_001",
    latitude="21.0285",
    longitude="105.8542",
    location="Khu rừng A"
} 0.92
```

### 3.3 Prometheus Metric Types


| Type          | Sử dụng cho              | Ví dụ                     |
| ------------- | ------------------------ | ------------------------- |
| **Gauge**     | Giá trị có thể tăng/giảm | confidence, device status |
| **Counter**   | Giá trị chỉ tăng         | total alerts count        |
| **Histogram** | Phân phối giá trị        | response time             |
| **Info**      | Metadata dạng label      | alert details             |


### 3.4 PromQL Queries Cho Geomap

```promql
# Query 1: Lấy tất cả fire alerts với location
fire_alert_info

# Query 2: Chỉ lấy alerts trong 1 giờ qua
fire_alert_info{} @ end() - fire_alert_info{} @ (end() - 1h)

# Query 3: Alerts với confidence > 0.8
fire_alert_info > 0.8

# Query 4: Latest alerts per device (sử dụng subquery)
last_over_time(fire_alert_info[1h])

# Query 5: Device status
device_status == 1
```

---

## 4. Backend Exporter

### 4.1 Requirements

```txt
# exporter/requirements.txt
prometheus_client==0.19.0
paho-mqtt==1.6.1
aiohttp==3.9.1
Pillow==10.2.0
python-dotenv==1.0.0
uvicorn==0.25.0
fastapi==0.109.0
requests==2.31.0
```

### 4.2 Metrics Module

```python
# exporter/metrics.py
from prometheus_client import Gauge, Counter, Info, REGISTRY, generate_latest
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import threading
import time

@dataclass
class FireAlert:
    alert_id: str
    device_id: str
    latitude: float
    longitude: float
    location: str
    confidence: float
    detection_class: str
    detected_at: str
    image_url: str
    timestamp: float = field(default_factory=time.time)

class FireDetectionMetrics:
    """
    Custom Prometheus metrics cho Fire Detection system.
    Cung cấp đầy đủ labels cần thiết cho Grafana Geomap.
    """

    def __init__(self, image_base_url: str = "http://localhost:8080/images"):
        self.image_base_url = image_base_url
        self.lock = threading.Lock()

        # Store active alerts (để hiển thị trên map)
        self.active_alerts: Dict[str, FireAlert] = {}

        # Store device status
        self.device_status: Dict[str, dict] = {}

        # Alert history (giữ trong 24h)
        self.alert_history: List[FireAlert] = []
        self.max_history_age = 24 * 3600  # 24 hours

        # ========================================
        # PROMETHEUS METRICS DEFINITIONS
        # ========================================

        # 1. Fire Alert Gauge (CHO GEOMAP)
        # Labels bắt buộc: latitude, longitude
        # Labels tùy chọn: hiển thị trong tooltip
        self.fire_alert_gauge = Gauge(
            'fire_alert_info',
            'Fire detection alert information with location',
            labelnames=[
                'alert_id',
                'device_id',
                'latitude',      # BẮT BUỘC cho Geomap
                'longitude',     # BẮT BUỘC cho Geomap
                'location',
                'class',
                'detected_at',
                'image_url'
            ]
        )

        # 2. Latest confidence per device (CHO GEOMAP)
        self.confidence_gauge = Gauge(
            'fire_confidence_latest',
            'Latest fire detection confidence per device',
            labelnames=[
                'device_id',
                'latitude',      # BẮT BUỘC cho Geomap
                'longitude',     # BẮT BUỘC cho Geomap
                'location'
            ]
        )

        # 3. Device status (CHO GEOMAP - hiển thị devices)
        self.device_status_gauge = Gauge(
            'fire_device_status',
            'Device online status (1=online, 0=offline)',
            labelnames=[
                'device_id',
                'latitude',      # BẮT BUỘC cho Geomap
                'longitude',     # BẮT BUỘC cho Geomap
                'location'
            ]
        )

        # 4. Total alerts counter
        self.alerts_total = Counter(
            'fire_alerts_total',
            'Total number of fire alerts',
            labelnames=['device_id', 'location', 'class']
        )

        # 5. Active alerts count
        self.active_alerts_gauge = Gauge(
            'fire_active_alerts_count',
            'Number of currently active fire alerts'
        )

        # 6. Alert processing time
        self.processing_time = Gauge(
            'fire_alert_processing_seconds',
            'Time to process fire alert'
        )

    def add_alert(self, alert: FireAlert):
        """Thêm alert mới và update metrics"""
        with self.lock:
            # Lưu alert
            self.active_alerts[alert.alert_id] = alert
            self.alert_history.append(alert)

            # Cleanup old history
            self._cleanup_old_alerts()

            # Update Prometheus metrics
            self._update_metrics(alert)

            print(f"Added alert: {alert.alert_id} at ({alert.latitude}, {alert.longitude})")

    def _update_metrics(self, alert: FireAlert):
        """Update tất cả Prometheus metrics"""

        # 1. Fire Alert Info (cho Geomap)
        # Note: 'class' is Python reserved keyword, use **{'class': value}
        self.fire_alert_gauge.labels(
            alert_id=alert.alert_id,
            device_id=alert.device_id,
            latitude=str(alert.latitude),      # Phải là string trong labels
            longitude=str(alert.longitude),    # Phải là string trong labels
            location=alert.location,
            detected_at=alert.detected_at,
            image_url=alert.image_url,
            **{'class': alert.detection_class}
        ).set(alert.confidence)

        # 2. Latest confidence per device
        self.confidence_gauge.labels(
            device_id=alert.device_id,
            latitude=str(alert.latitude),
            longitude=str(alert.longitude),
            location=alert.location
        ).set(alert.confidence)

        # 3. Total alerts counter
        self.alerts_total.labels(
            device_id=alert.device_id,
            location=alert.location,
            **{'class': alert.detection_class}
        ).inc()

        # 4. Active alerts count
        self.active_alerts_gauge.set(len(self.active_alerts))

    def update_device_status(self, device_id: str, latitude: float,
                            longitude: float, location: str, is_online: bool):
        """Update device status"""
        with self.lock:
            self.device_status[device_id] = {
                'latitude': latitude,
                'longitude': longitude,
                'location': location,
                'is_online': is_online,
                'last_seen': time.time()
            }

            self.device_status_gauge.labels(
                device_id=device_id,
                latitude=str(latitude),
                longitude=str(longitude),
                location=location
            ).set(1 if is_online else 0)

    def remove_alert(self, alert_id: str):
        """Xóa alert (khi đã acknowledge)"""
        with self.lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts.pop(alert_id)

                # Remove from Prometheus
                try:
                    self.fire_alert_gauge.remove(
                        alert.alert_id,
                        alert.device_id,
                        str(alert.latitude),
                        str(alert.longitude),
                        alert.location,
                        alert.detection_class,
                        alert.detected_at,
                        alert.image_url
                    )
                except KeyError:
                    pass

                self.active_alerts_gauge.set(len(self.active_alerts))

    def _cleanup_old_alerts(self):
        """Cleanup alerts cũ hơn max_history_age"""
        current_time = time.time()
        cutoff_time = current_time - self.max_history_age

        # Cleanup history
        self.alert_history = [
            a for a in self.alert_history
            if a.timestamp > cutoff_time
        ]

        # Cleanup active alerts (giữ trong 1 giờ)
        active_cutoff = current_time - 3600
        expired_ids = [
            aid for aid, alert in self.active_alerts.items()
            if alert.timestamp < active_cutoff
        ]

        for alert_id in expired_ids:
            self.remove_alert(alert_id)

    def get_all_alerts(self) -> List[FireAlert]:
        """Lấy tất cả active alerts"""
        with self.lock:
            return list(self.active_alerts.values())

    def get_metrics(self) -> bytes:
        """Generate Prometheus metrics output"""
        return generate_latest(REGISTRY)


# Singleton instance
_metrics_instance: Optional[FireDetectionMetrics] = None

def get_metrics() -> FireDetectionMetrics:
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = FireDetectionMetrics()
    return _metrics_instance
```

### 4.3 MQTT Handler

```python
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
```

### 4.4 Notification Service

```python
# exporter/notification.py
import os
import requests
from typing import Optional
from metrics import FireAlert

class NotificationService:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

    def send_alert(self, alert: FireAlert, image_path: Optional[str] = None):
        """Send alert notification via configured channels"""
        if self.telegram_token and self.telegram_chat_id:
            self._send_telegram(alert, image_path)

    def _send_telegram(self, alert: FireAlert, image_path: Optional[str]):
        """Send notification via Telegram"""
        message = self._format_message(alert)

        # Send to multiple chat IDs if configured
        chat_ids = [cid.strip() for cid in self.telegram_chat_id.split(',')]

        for chat_id in chat_ids:
            try:
                if image_path and os.path.exists(image_path):
                    # Send with photo
                    url = f"https://api.telegram.org/bot{self.telegram_token}/sendPhoto"
                    with open(image_path, 'rb') as photo:
                        files = {'photo': photo}
                        data = {
                            'chat_id': chat_id,
                            'caption': message,
                            'parse_mode': 'HTML'
                        }
                        response = requests.post(url, files=files, data=data, timeout=30)
                else:
                    # Send text only
                    url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                    data = {
                        'chat_id': chat_id,
                        'text': message,
                        'parse_mode': 'HTML'
                    }
                    response = requests.post(url, json=data, timeout=30)

                if response.status_code == 200:
                    print(f"Telegram notification sent to {chat_id}")
                else:
                    print(f"Telegram error: {response.text}")

            except Exception as e:
                print(f"Failed to send Telegram to {chat_id}: {e}")

    def _format_message(self, alert: FireAlert) -> str:
        """Format alert message"""
        google_maps_url = f"https://maps.google.com/?q={alert.latitude},{alert.longitude}"

        return f"""
🔥 <b>CẢNH BÁO PHÁT HIỆN CHÁY RỪNG!</b>

📍 <b>Vị trí:</b> {alert.location}
🌍 <b>Tọa độ:</b> <a href="{google_maps_url}">{alert.latitude:.6f}, {alert.longitude:.6f}</a>
📊 <b>Độ tin cậy:</b> {alert.confidence*100:.1f}%
🔍 <b>Loại:</b> {alert.detection_class}
⏰ <b>Thời gian:</b> {alert.detected_at}

🆔 Alert ID: <code>{alert.alert_id}</code>
📡 Device: <code>{alert.device_id}</code>

⚠️ Vui lòng kiểm tra và xử lý kịp thời!
"""
```

### 4.5 Main Application

```python
# exporter/main.py
import os
import uvicorn
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import threading
import time

from metrics import get_metrics, FireAlert
from mqtt_handler import MQTTHandler

# Global instances
mqtt_handler: MQTTHandler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mqtt_handler

    # Startup
    print("Starting Fire Detection Exporter...")

    mqtt_handler = MQTTHandler(
        broker=os.getenv('MQTT_BROKER', 'localhost'),
        port=int(os.getenv('MQTT_PORT', 1883)),
        images_dir=os.getenv('IMAGES_DIR', './images'),
        image_base_url=os.getenv('IMAGE_BASE_URL', 'http://localhost:8080/images')
    )
    mqtt_handler.connect()

    yield

    # Shutdown
    print("Shutting down...")
    if mqtt_handler:
        mqtt_handler.disconnect()

app = FastAPI(
    title="Fire Detection Prometheus Exporter",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "running", "service": "Fire Detection Exporter"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_handler.connected if mqtt_handler else False
    }

@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    Grafana sẽ query endpoint này thông qua Prometheus.
    """
    metrics_data = get_metrics().get_metrics()
    return Response(
        content=metrics_data,
        media_type="text/plain; charset=utf-8"
    )

@app.get("/alerts")
async def get_alerts():
    """Get all active alerts (for debugging)"""
    alerts = get_metrics().get_all_alerts()
    return {
        "count": len(alerts),
        "alerts": [
            {
                "alert_id": a.alert_id,
                "device_id": a.device_id,
                "latitude": a.latitude,
                "longitude": a.longitude,
                "location": a.location,
                "confidence": a.confidence,
                "class": a.detection_class,
                "detected_at": a.detected_at,
                "image_url": a.image_url
            }
            for a in alerts
        ]
    }

# For testing: Simulate an alert
@app.post("/test-alert")
async def test_alert():
    """Send a test alert (for development)"""
    import uuid
    from datetime import datetime

    alert = FireAlert(
        alert_id=str(uuid.uuid4())[:8],
        device_id="test_device_001",
        latitude=21.0285 + (hash(str(time.time())) % 100) / 10000,
        longitude=105.8542 + (hash(str(time.time())) % 100) / 10000,
        location="Test Location - Khu vực rừng thử nghiệm",
        confidence=0.85 + (hash(str(time.time())) % 15) / 100,
        detection_class="fire",
        detected_at=datetime.now().isoformat(),
        image_url=""
    )

    get_metrics().add_alert(alert)

    return {"message": "Test alert created", "alert_id": alert.alert_id}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 4.6 Dockerfile

```dockerfile
# exporter/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY *.py .

# Create images directory
RUN mkdir -p /app/images

EXPOSE 8000

CMD ["python", "main.py"]
```

---

## 5. Cấu Hình Prometheus

### 5.1 Prometheus Config

```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s          # Scrape mỗi 15 giây
  evaluation_interval: 15s      # Evaluate rules mỗi 15 giây
  external_labels:
    monitor: 'fire-detection'

# Alertmanager configuration
# Sử dụng container name trong shared Docker network: fire-detection-network
alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - fire-alertmanager:9093

# Load rules
rule_files:
  - /etc/prometheus/alerts.yml

# Scrape configurations
scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Fire Detection Exporter
  # Container name: fire-exporter trong network: fire-detection-network
  - job_name: 'fire_detection'
    scrape_interval: 10s        # Scrape thường xuyên hơn để real-time
    static_configs:
      - targets: ['fire-exporter:8000']
    metrics_path: /metrics
```

### 5.2 Alert Rules

```yaml
# prometheus/alerts.yml
groups:
  - name: fire_detection_alerts
    rules:
      # Alert khi phát hiện cháy mới
      - alert: FireDetected
        expr: fire_alert_info > 0.5
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Fire detected at {{ $labels.location }}"
          description: |
            Fire detected with confidence {{ printf "%.1f" $value }}%
            Location: {{ $labels.location }}
            Coordinates: {{ $labels.latitude }}, {{ $labels.longitude }}
            Device: {{ $labels.device_id }}
            Image: {{ $labels.image_url }}

      # Alert khi confidence cao
      - alert: HighConfidenceFire
        expr: fire_alert_info > 0.9
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "HIGH CONFIDENCE fire at {{ $labels.location }}"
          description: 'Confidence: {{ printf "%.1f" $value }}%'

      # Alert khi device offline
      - alert: DeviceOffline
        expr: fire_device_status == 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Device {{ $labels.device_id }} is offline"
          description: "Device at {{ $labels.location }} has been offline for 5 minutes"

      # Alert khi có nhiều alerts trong thời gian ngắn
      - alert: MultipleFireAlerts
        expr: sum(increase(fire_alerts_total[10m])) > 5
        for: 0m
        labels:
          severity: warning
        annotations:
          summary: "Multiple fire alerts detected"
          description: "{{ $value }} alerts in the last 10 minutes"
```

---

## 6. Cấu Hình Grafana Geomap

### 6.1 Datasource Provisioning

```yaml
# grafana/provisioning/datasources/prometheus.yml
# Sử dụng container names trong shared Docker network: fire-detection-network
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    uid: prometheus
    access: proxy
    url: http://fire-prometheus:9090
    isDefault: true
    editable: false

  - name: Alertmanager
    type: alertmanager
    uid: alertmanager
    access: proxy
    url: http://fire-alertmanager:9093
    jsonData:
      implementation: prometheus
```

### 6.2 Dashboard Provisioning

```yaml
# grafana/provisioning/dashboards/dashboard.yml
apiVersion: 1

providers:
  - name: 'Fire Detection Dashboards'
    orgId: 1
    folder: 'Fire Detection'
    folderUid: 'fire-detection'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

### 6.3 Dashboard JSON (Fire Detection Geomap)

```json
{
  "annotations": {
    "list": []
  },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "liveNow": true,
  "panels": [
    {
      "title": "🔥 Fire Detection Map",
      "type": "geomap",
      "gridPos": {
        "h": 16,
        "w": 16,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "fire_alert_info",
          "format": "table",
          "instant": true,
          "legendFormat": "",
          "refId": "A"
        }
      ],
      "options": {
        "view": {
          "id": "coords",
          "lat": 16.0,
          "lon": 108.0,
          "zoom": 6
        },
        "basemap": {
          "config": {},
          "name": "OpenStreetMap",
          "type": "osm-standard"
        },
        "controls": {
          "mouseWheelZoom": true,
          "showAttribution": true,
          "showDebug": false,
          "showMeasure": false,
          "showScale": true,
          "showZoom": true
        },
        "layers": [
          {
            "config": {
              "showLegend": true,
              "style": {
                "color": {
                  "field": "Value",
                  "fixed": "red"
                },
                "opacity": 0.8,
                "rotation": {
                  "fixed": 0,
                  "max": 360,
                  "min": -360,
                  "mode": "mod"
                },
                "size": {
                  "field": "Value",
                  "fixed": 10,
                  "max": 20,
                  "min": 5
                },
                "symbol": {
                  "fixed": "img/icons/marker/circle.svg",
                  "mode": "fixed"
                },
                "symbolAlign": {
                  "horizontal": "center",
                  "vertical": "center"
                },
                "text": {
                  "field": "location",
                  "fixed": "",
                  "mode": "field"
                },
                "textConfig": {
                  "fontSize": 12,
                  "offsetX": 0,
                  "offsetY": -15,
                  "textAlign": "center",
                  "textBaseline": "middle"
                }
              }
            },
            "location": {
              "latitude": "latitude",
              "longitude": "longitude",
              "mode": "coords"
            },
            "name": "Fire Alerts",
            "tooltip": true,
            "type": "markers"
          }
        ],
        "tooltip": {
          "mode": "details"
        }
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "yellow",
                "value": null
              },
              {
                "color": "orange",
                "value": 0.7
              },
              {
                "color": "red",
                "value": 0.85
              }
            ]
          }
        },
        "overrides": []
      }
    },
    {
      "title": "📊 Alert Statistics",
      "type": "stat",
      "gridPos": {
        "h": 4,
        "w": 8,
        "x": 16,
        "y": 0
      },
      "id": 2,
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "expr": "fire_active_alerts_count",
          "legendFormat": "Active Alerts",
          "refId": "A"
        }
      ],
      "options": {
        "colorMode": "background",
        "graphMode": "none",
        "justifyMode": "center",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": ["lastNotNull"],
          "fields": "",
          "values": false
        },
        "textMode": "auto"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "yellow",
                "value": 1
              },
              {
                "color": "red",
                "value": 5
              }
            ]
          }
        }
      }
    },
    {
      "title": "📈 Alerts Over Time",
      "type": "timeseries",
      "gridPos": {
        "h": 6,
        "w": 8,
        "x": 16,
        "y": 4
      },
      "id": 3,
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "expr": "increase(fire_alerts_total[1h])",
          "legendFormat": "{{ device_id }}",
          "refId": "A"
        }
      ],
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom"
        }
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisLabel": "",
            "axisPlacement": "auto",
            "drawStyle": "line",
            "fillOpacity": 20,
            "lineWidth": 2,
            "pointSize": 5,
            "showPoints": "auto"
          }
        }
      }
    },
    {
      "title": "🔴 Recent Alerts",
      "type": "table",
      "gridPos": {
        "h": 6,
        "w": 8,
        "x": 16,
        "y": 10
      },
      "id": 4,
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "expr": "fire_alert_info",
          "format": "table",
          "instant": true,
          "refId": "A"
        }
      ],
      "transformations": [
        {
          "id": "organize",
          "options": {
            "excludeByName": {
              "Time": true,
              "__name__": true,
              "instance": true,
              "job": true
            },
            "renameByName": {
              "Value": "Confidence",
              "alert_id": "Alert ID",
              "device_id": "Device",
              "location": "Location",
              "detected_at": "Time",
              "image_url": "Image"
            }
          }
        }
      ],
      "options": {
        "showHeader": true,
        "cellHeight": "sm"
      },
      "fieldConfig": {
        "defaults": {
          "custom": {
            "align": "auto",
            "cellOptions": {
              "type": "auto"
            }
          }
        },
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "Confidence"
            },
            "properties": [
              {
                "id": "unit",
                "value": "percentunit"
              },
              {
                "id": "custom.cellOptions",
                "value": {
                  "mode": "gradient",
                  "type": "gauge"
                }
              },
              {
                "id": "thresholds",
                "value": {
                  "mode": "absolute",
                  "steps": [
                    {"color": "yellow", "value": null},
                    {"color": "orange", "value": 0.7},
                    {"color": "red", "value": 0.85}
                  ]
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "Image"
            },
            "properties": [
              {
                "id": "custom.cellOptions",
                "value": {
                  "type": "data-links"
                }
              },
              {
                "id": "links",
                "value": [
                  {
                    "title": "View Image",
                    "url": "${__value.text}"
                  }
                ]
              }
            ]
          }
        ]
      }
    },
    {
      "title": "📡 Device Status",
      "type": "geomap",
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 0,
        "y": 16
      },
      "id": 5,
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "expr": "fire_device_status",
          "format": "table",
          "instant": true,
          "refId": "A"
        }
      ],
      "options": {
        "view": {
          "id": "coords",
          "lat": 16.0,
          "lon": 108.0,
          "zoom": 6
        },
        "basemap": {
          "type": "osm-standard"
        },
        "layers": [
          {
            "config": {
              "style": {
                "color": {
                  "field": "Value",
                  "fixed": "green"
                },
                "size": {
                  "fixed": 8
                },
                "symbol": {
                  "fixed": "img/icons/marker/square.svg"
                }
              }
            },
            "location": {
              "latitude": "latitude",
              "longitude": "longitude",
              "mode": "coords"
            },
            "name": "Devices",
            "tooltip": true,
            "type": "markers"
          }
        ]
      },
      "fieldConfig": {
        "defaults": {
          "thresholds": {
            "steps": [
              {"color": "red", "value": null},
              {"color": "green", "value": 1}
            ]
          }
        }
      }
    },
    {
      "title": "📊 Confidence Distribution",
      "type": "histogram",
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 8,
        "y": 16
      },
      "id": 6,
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "expr": "fire_confidence_latest",
          "format": "time_series",
          "refId": "A"
        }
      ]
    },
    {
      "title": "🔥 Total Alerts by Device",
      "type": "piechart",
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 16,
        "y": 16
      },
      "id": 7,
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "expr": "sum by (device_id) (fire_alerts_total)",
          "legendFormat": "{{ device_id }}",
          "refId": "A"
        }
      ]
    }
  ],
  "refresh": "10s",
  "schemaVersion": 38,
  "tags": ["fire-detection", "geomap"],
  "templating": {
    "list": [
      {
        "name": "device",
        "type": "query",
        "datasource": {
          "type": "prometheus",
          "uid": "prometheus"
        },
        "query": "label_values(fire_alert_info, device_id)",
        "includeAll": true,
        "multi": true
      }
    ]
  },
  "time": {
    "from": "now-1h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "Fire Detection Dashboard",
  "uid": "fire-detection-main",
  "version": 1
}
```

### 6.4 Cấu Hình Geomap Chi Tiết

> **QUAN TRỌNG**: Để Geomap hiển thị đúng, cần cấu hình như sau:

#### Bước 1: Cấu hình Query

```yaml
# Trong Grafana Panel Editor > Query

Query: fire_alert_info
Format: Table
Type: Instant

# Kết quả sẽ có các cột:
# - Time
# - Value (confidence score)
# - alert_id
# - device_id
# - latitude
# - longitude
# - location
# - class
# - detected_at
# - image_url
```

#### Bước 2: Cấu hình Location

```yaml
# Panel Options > Layers > Layer 1 > Location

Mode: Coords
Latitude field: latitude      # Tên label trong metric
Longitude field: longitude    # Tên label trong metric
```

#### Bước 3: Cấu hình Style

```yaml
# Panel Options > Layers > Layer 1 > Style

Size:
  Mode: Field
  Field: Value              # Sử dụng confidence làm size
  Min: 5
  Max: 20

Color:
  Mode: Thresholds
  Field: Value
  Thresholds:
    - 0: yellow
    - 0.7: orange
    - 0.85: red

Symbol: Circle hoặc Custom icon

Text:
  Mode: Field
  Field: location           # Hiển thị tên location
```

#### Bước 4: Cấu hình Tooltip

```yaml
# Panel Options > Tooltip

Mode: Details              # Hiển thị tất cả fields

# Tooltip sẽ hiển thị:
# - alert_id
# - device_id
# - location
# - confidence
# - detected_at
# - image_url (clickable)
```

### 6.5 Data Format Requirements

```
┌─────────────────────────────────────────────────────────────────────────────┐
│               GRAFANA GEOMAP - YÊU CẦU DATA FORMAT                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PROMETHEUS METRIC PHẢI CÓ:                                                 │
│                                                                              │
│  1. Labels bắt buộc:                                                        │
│     ├── latitude="21.0285"     (string, số thực)                           │
│     └── longitude="105.8542"   (string, số thực)                           │
│                                                                              │
│  2. Value:                                                                  │
│     └── Số thực (ví dụ: 0.92 cho confidence)                               │
│                                                                              │
│  3. Labels tùy chọn (hiển thị trong tooltip):                              │
│     ├── location="Khu rừng A"                                               │
│     ├── device_id="edge_001"                                                │
│     ├── alert_id="abc123"                                                   │
│     ├── detected_at="2024-01-15T10:30:00Z"                                 │
│     └── image_url="http://..."                                              │
│                                                                              │
│  VÍ DỤ METRIC:                                                              │
│  fire_alert_info{                                                           │
│    alert_id="abc123",                                                       │
│    device_id="edge_001",                                                    │
│    latitude="21.0285",          ◄── BẮT BUỘC                               │
│    longitude="105.8542",        ◄── BẮT BUỘC                               │
│    location="Khu rừng A",                                                   │
│    class="fire",                                                            │
│    detected_at="2024-01-15T10:30:00Z",                                     │
│    image_url="http://localhost:8080/images/abc123.jpg"                     │
│  } 0.92                         ◄── CONFIDENCE VALUE                       │
│                                                                              │
│  QUERY FORMAT:                                                              │
│  ├── Format: Table (không phải Time series)                                │
│  └── Type: Instant (không phải Range)                                      │
│                                                                              │
│  GEOMAP CONFIG:                                                             │
│  ├── Location Mode: Coords                                                  │
│  ├── Latitude field: latitude                                               │
│  └── Longitude field: longitude                                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Push Notification

### 7.1 Notification Flow

```
Fire Alert ──▶ Exporter ──▶ Telegram Bot
                  │
                  └──▶ Prometheus ──▶ Alertmanager ──▶ Telegram/Email
```

### 7.2 Telegram Bot Setup

```bash
# Bước 1: Tạo Bot
# 1. Mở Telegram, tìm @BotFather
# 2. Gửi /newbot
# 3. Đặt tên: Fire Detection Alert Bot
# 4. Nhận token: 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ

# Bước 2: Lấy Chat ID
# Option A: Chat trực tiếp với bot
# 1. Gửi tin nhắn cho bot
# 2. Truy cập: https://api.telegram.org/bot<TOKEN>/getUpdates
# 3. Tìm "chat":{"id": 123456789}

# Option B: Thêm bot vào group
# 1. Thêm bot vào group
# 2. Gửi tin nhắn trong group
# 3. Truy cập API getUpdates
# 4. Chat ID sẽ là số âm: -1001234567890

# Bước 3: Test bot
curl -X POST "https://api.telegram.org/bot8696341608:AAFc0dNq_FDS-_7IeyZA8x8UIollLf0tugw/sendMessage" \
  -d "chat_id=670269618" \
  -d "text=Test message from Fire Detection System"
```

### 7.3 Environment Variables

```env
# .env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=-1001234567890

# Multiple chat IDs (comma separated)
TELEGRAM_CHAT_ID=-1001234567890,123456789,987654321
```

---

## 8. Alertmanager Integration

### 8.1 Alertmanager Config

```yaml
# alertmanager/alertmanager.yml
global:
  resolve_timeout: 5m
  telegram_api_url: "https://api.telegram.org"

route:
  group_by: ['alertname', 'device_id']
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 1h
  receiver: 'telegram-notifications'

  routes:
    # Critical alerts - immediate notification
    - match:
        severity: critical
      receiver: 'telegram-critical'
      group_wait: 0s
      repeat_interval: 15m

    # Warning alerts
    - match:
        severity: warning
      receiver: 'telegram-notifications'
      group_wait: 30s

receivers:
  - name: 'telegram-critical'
    telegram_configs:
      - bot_token: '${TELEGRAM_BOT_TOKEN}'
        chat_id: ${TELEGRAM_CHAT_ID}
        parse_mode: 'HTML'
        message: |
          🔥🔥🔥 <b>CRITICAL FIRE ALERT!</b> 🔥🔥🔥

          <b>Alert:</b> {{ .GroupLabels.alertname }}
          <b>Status:</b> {{ .Status | toUpper }}

          {{ range .Alerts }}
          ━━━━━━━━━━━━━━━━━━━━━━
          📍 <b>Location:</b> {{ .Labels.location }}
          🌍 <b>Coordinates:</b> {{ .Labels.latitude }}, {{ .Labels.longitude }}
          📊 <b>Confidence:</b> {{ .Annotations.confidence }}
          📡 <b>Device:</b> {{ .Labels.device_id }}
          ⏰ <b>Time:</b> {{ .StartsAt.Format "2006-01-02 15:04:05" }}

          🖼 <a href="{{ .Labels.image_url }}">View Image</a>
          🗺 <a href="https://maps.google.com/?q={{ .Labels.latitude }},{{ .Labels.longitude }}">View on Map</a>
          {{ end }}

          ⚠️ <b>Immediate action required!</b>

  - name: 'telegram-notifications'
    telegram_configs:
      - bot_token: '${TELEGRAM_BOT_TOKEN}'
        chat_id: ${TELEGRAM_CHAT_ID}
        parse_mode: 'HTML'
        message: |
          🚨 <b>Fire Detection Alert</b>

          <b>Alert:</b> {{ .GroupLabels.alertname }}
          <b>Status:</b> {{ .Status }}

          {{ range .Alerts }}
          • {{ .Labels.location }}: {{ .Annotations.summary }}
          {{ end }}

# Inhibit rules
inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'device_id']
```

### 8.2 Alert Flow

```
Prometheus scrapes metrics
        │
        ▼
Evaluates alert rules (alerts.yml)
        │
        ▼
Alert triggered ──▶ Alertmanager
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   Telegram          Email            Webhook
```

---

## 9. Complete Docker Setup

### 9.1 Mosquitto Config

```conf
# mosquitto/mosquitto.conf
listener 1883
listener 9001
protocol websockets

allow_anonymous true
persistence true
persistence_location /mosquitto/data/

log_dest file /mosquitto/log/mosquitto.log
log_type all
```

### 9.2 Nginx Config (Serve Images)

```nginx
# nginx/nginx.conf
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    server {
        listen 80;
        server_name localhost;

        # Serve images
        location /images/ {
            alias /usr/share/nginx/html/images/;
            autoindex on;

            # CORS headers
            add_header Access-Control-Allow-Origin *;
            add_header Access-Control-Allow-Methods 'GET, OPTIONS';

            # Cache
            expires 1d;
            add_header Cache-Control "public, immutable";
        }
    }
}
```

### 9.3 Grafana Config

```ini
# grafana/grafana.ini
[server]
root_url = http://localhost:3000

[security]
admin_user = admin
admin_password = admin123

[auth.anonymous]
enabled = false

[alerting]
# Disable legacy alerting (use unified alerting instead)
enabled = false

[unified_alerting]
enabled = true

[feature_toggles]
enable = publicDashboards
```

> **LƯU Ý QUAN TRỌNG**: Không được bật cả `[alerting]` và `[unified_alerting]` cùng lúc.
> Grafana 10+ yêu cầu chỉ sử dụng một trong hai. Khuyến nghị sử dụng `unified_alerting`.

### 9.4 Standalone Docker Deployment

Mỗi service có thể chạy độc lập với script `run.sh` riêng:

```bash
# Cấu trúc mỗi service
fire-detection-monitoring/
├── mosquitto/
│   ├── Dockerfile
│   └── run.sh          # ./run.sh {build|start|stop|logs|status}
├── exporter/
│   ├── Dockerfile
│   └── run.sh
├── prometheus/
│   ├── Dockerfile
│   ├── entrypoint.sh   # Custom entrypoint cho dynamic config
│   └── run.sh
├── alertmanager/
│   ├── Dockerfile
│   ├── entrypoint.sh   # Custom entrypoint cho env var substitution
│   └── run.sh
├── grafana/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── run.sh
├── nginx/
│   ├── Dockerfile
│   └── run.sh
└── run-all.sh          # Master script để quản lý tất cả services
```

**Shared Docker Network:**
Tất cả containers sử dụng chung network `fire-detection-network` để giao tiếp với nhau bằng container name.

```bash
# Chạy từng service riêng lẻ
cd fire-detection-monitoring
./mosquitto/run.sh start
./exporter/run.sh start
./prometheus/run.sh start
./alertmanager/run.sh start
./grafana/run.sh start
./nginx/run.sh start

# Hoặc chạy tất cả cùng lúc
./run-all.sh start

# Xem status
./run-all.sh status

# Stop tất cả
./run-all.sh stop
```

### 9.5 Start Services (Docker Compose)

```bash
# 1. Clone project và tạo directories
mkdir -p fire-detection-monitoring/{exporter,prometheus,alertmanager,grafana/provisioning/{datasources,dashboards},mosquitto,nginx,images}

# 2. Tạo .env file
cat > .env << 'EOF'
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
EOF

# 3. Copy các config files vào đúng vị trí
# (Copy nội dung từ các sections ở trên)

# 4. Build và start
docker-compose up -d --build

# 5. Kiểm tra logs
docker-compose logs -f

# 6. Kiểm tra status
docker-compose ps
```

---

## 10. Testing & Verification

### 10.1 Test MQTT Alert

```bash
# Gửi test alert qua MQTT
mosquitto_pub -h localhost -t wildfire/alerts -m '{
  "alert_id": "test_001",
  "device_id": "edge_device_001",
  "timestamp": "2024-01-15T10:30:00Z",
  "location": {
    "lat": 21.0285,
    "lon": 105.8542,
    "name": "Khu rừng A - Điểm giám sát 1"
  },
  "detections": [
    {"class": "fire", "confidence": 0.92, "bbox": [100, 100, 200, 200]}
  ],
  "confidence_max": 0.92,
  "image_base64": ""
}'
```

### 10.2 Test Exporter API

```bash
# Test health
curl http://localhost:8000/health

# Test metrics endpoint
curl http://localhost:8000/metrics

# Test alerts list
curl http://localhost:8000/alerts

# Create test alert
curl -X POST http://localhost:8000/test-alert
```

### 10.3 Verify Prometheus

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Query metrics
curl 'http://localhost:9090/api/v1/query?query=fire_alert_info'

# Check alerts
curl http://localhost:9090/api/v1/alerts
```

### 10.4 Test Grafana

```bash
# 1. Mở browser: http://localhost:3000
# 2. Login: admin / admin123
# 3. Vào Dashboards > Fire Detection
# 4. Verify Geomap hiển thị markers
```

### 10.5 Test Script

```python
# test_system.py
import requests
import json
import paho.mqtt.client as mqtt
import time
import random

MQTT_BROKER = "localhost"
EXPORTER_URL = "http://localhost:8000"
PROMETHEUS_URL = "http://localhost:9090"

def test_mqtt_alert():
    """Send test alert via MQTT"""
    client = mqtt.Client()
    client.connect(MQTT_BROKER, 1883)

    # Locations in Vietnam for testing
    locations = [
        {"lat": 21.0285, "lon": 105.8542, "name": "Hà Nội - Khu vực rừng 1"},
        {"lat": 16.0544, "lon": 108.2022, "name": "Đà Nẵng - Khu vực rừng 2"},
        {"lat": 10.8231, "lon": 106.6297, "name": "TP.HCM - Khu vực rừng 3"},
        {"lat": 21.3891, "lon": 103.0169, "name": "Lào Cai - Khu vực rừng 4"},
    ]

    location = random.choice(locations)
    confidence = 0.7 + random.random() * 0.25  # 0.7 - 0.95

    alert = {
        "alert_id": f"test_{int(time.time())}",
        "device_id": f"edge_device_{random.randint(1, 5):03d}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "location": location,
        "detections": [
            {"class": "fire", "confidence": confidence}
        ],
        "confidence_max": confidence
    }

    client.publish("wildfire/alerts", json.dumps(alert))
    client.disconnect()

    print(f"Sent alert: {alert['alert_id']} at {location['name']}")
    return alert

def test_exporter_metrics():
    """Verify exporter metrics"""
    response = requests.get(f"{EXPORTER_URL}/metrics")
    assert response.status_code == 200

    metrics_text = response.text
    assert "fire_alert_info" in metrics_text
    print("Exporter metrics OK")

def test_prometheus_query():
    """Query Prometheus for fire alerts"""
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": "fire_alert_info"}
    )
    assert response.status_code == 200

    data = response.json()
    results = data.get("data", {}).get("result", [])
    print(f"Prometheus has {len(results)} fire alerts")

def main():
    print("=== Testing Fire Detection System ===\n")

    # Send multiple test alerts
    print("1. Sending test alerts...")
    for i in range(3):
        test_mqtt_alert()
        time.sleep(1)

    # Wait for processing
    time.sleep(5)

    # Test exporter
    print("\n2. Testing exporter...")
    test_exporter_metrics()

    # Test Prometheus
    print("\n3. Testing Prometheus...")
    test_prometheus_query()

    print("\n=== All tests passed! ===")
    print("\nOpen Grafana at http://localhost:3000 to view the dashboard")

if __name__ == "__main__":
    main()
```

### 10.6 Checklist Hoàn Thành

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CHECKLIST HOÀN THÀNH                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [ ] Docker Compose khởi động thành công tất cả services                    │
│  [ ] MQTT Broker nhận messages từ edge devices                              │
│  [ ] Exporter expose metrics đúng format                                    │
│  [ ] Prometheus scrape metrics thành công                                   │
│  [ ] Grafana Geomap hiển thị markers với vị trí đúng                       │
│  [ ] Tooltip hiển thị đầy đủ thông tin (confidence, location, image)       │
│  [ ] Statistics panels hiển thị đúng                                        │
│  [ ] Telegram notification gửi thành công                                   │
│  [ ] Alertmanager trigger alerts đúng                                       │
│  [ ] Images được serve và hiển thị đúng                                     │
│  [ ] Real-time update hoạt động (refresh 10s)                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Troubleshooting

### 11.1 Common Issues

#### Grafana: "Datasource prometheus was not found"
**Nguyên nhân**: Dashboard JSON reference datasource uid không khớp với config.
**Giải pháp**: Thêm `uid: prometheus` trong datasource provisioning:
```yaml
datasources:
  - name: Prometheus
    type: prometheus
    uid: prometheus  # Thêm dòng này
```

#### Grafana: "Legacy and unified alerting cannot both be enabled"
**Nguyên nhân**: Cả hai alerting mode đều enabled.
**Giải pháp**: Disable legacy alerting trong `grafana.ini`:
```ini
[alerting]
enabled = false

[unified_alerting]
enabled = true
```

#### Prometheus: "permission denied" khi start
**Nguyên nhân**: Data directory không có quyền ghi cho user `nobody`.
**Giải pháp**: Fix permissions:
```bash
chmod 777 prometheus/data
```

#### Prometheus: Target "down" - cannot scrape exporter
**Nguyên nhân**: Container name không đúng hoặc không cùng Docker network.
**Giải pháp**:
1. Kiểm tra containers cùng network: `docker network inspect fire-detection-network`
2. Sử dụng đúng container name trong config: `fire-exporter:8000`

#### Alertmanager: YAML parse error với chat_id
**Nguyên nhân**: `${TELEGRAM_CHAT_ID}` là string nhưng `chat_id` cần integer.
**Giải pháp**: Sử dụng entrypoint script để substitute env vars với `sed`.

#### Python: "class" is a reserved keyword
**Nguyên nhân**: Không thể sử dụng `class=value` trong function call.
**Giải pháp**: Sử dụng `**{'class': value}`:
```python
self.fire_alert_gauge.labels(
    ...,
    **{'class': alert.detection_class}
).set(alert.confidence)
```

### 11.2 Debug Commands

```bash
# Check container logs
docker logs fire-exporter
docker logs fire-prometheus
docker logs fire-alertmanager
docker logs fire-grafana

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check exporter metrics
curl http://localhost:8000/metrics | grep fire_alert

# Check exporter alerts
curl http://localhost:8000/alerts

# Test Prometheus query
curl 'http://localhost:9090/api/v1/query?query=fire_alert_info'

# Check Docker network
docker network inspect fire-detection-network

# Check all running containers
docker ps --filter "name=fire-"
```

---

## Tài Liệu Tham Khảo

1. [Grafana Geomap Documentation](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/geomap/)
2. [Prometheus Data Model](https://prometheus.io/docs/concepts/data_model/)
3. [Prometheus Client Python](https://github.com/prometheus/client_python)
4. [Alertmanager Configuration](https://prometheus.io/docs/alerting/latest/configuration/)
5. [Telegram Bot API](https://core.telegram.org/bots/api)

