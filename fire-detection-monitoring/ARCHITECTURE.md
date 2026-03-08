# Fire Detection Monitoring System - Architecture Documentation

## Overview

A real-time wildfire detection and monitoring system designed for IoT edge devices in Vietnam's forest regions. The system processes fire/smoke detection alerts from edge devices, provides visualization through Grafana dashboards with geo-mapping capabilities, and sends immediate notifications via Telegram.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FIRE DETECTION MONITORING SYSTEM                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     MQTT      ┌──────────────┐     HTTP      ┌──────────────┐
│  Edge Device │──────────────▶│   Mosquitto  │◀─────────────▶│   Exporter   │
│  (IoT/Camera)│   :1883       │  MQTT Broker │               │  (FastAPI)   │
└──────────────┘               └──────────────┘               └──────┬───────┘
                                                                     │
                                                                     │ /metrics
                                                                     ▼
┌──────────────┐               ┌──────────────┐     Scrape    ┌──────────────┐
│   Telegram   │◀──────────────│ Alertmanager │◀──────────────│  Prometheus  │
│   Bot API    │  Reminders    │    :9093     │    Alerts     │    :9090     │
└──────────────┘               └──────────────┘               └──────┬───────┘
       ▲                                                             │
       │                                                             │ Query
       │ Immediate                                                   ▼
       │ Notification                                         ┌──────────────┐
       │                                                      │   Grafana    │
       └──────────────────────────────────────────────────────│    :3000     │
                              (via Exporter)                  └──────────────┘
                                                                     │
                                                                     │ Image URLs
                                                                     ▼
                                                              ┌──────────────┐
                                                              │    Nginx     │
                                                              │    :8080     │
                                                              │ (Image Server)│
                                                              └──────────────┘
```

## Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Message Broker** | Eclipse Mosquitto | 2.x | MQTT messaging for IoT devices |
| **Backend API** | FastAPI + Uvicorn | 0.109.0 | Prometheus metrics exporter |
| **Metrics** | Prometheus | 2.48.0 | Time-series metrics storage |
| **Alerting** | Alertmanager | 0.26.0 | Alert routing and reminders |
| **Visualization** | Grafana | 10.2.2 | Dashboards and geo-mapping |
| **Image Server** | Nginx | Alpine | Static image serving |
| **Notifications** | Telegram Bot API | - | Real-time alert notifications |
| **Container Runtime** | Docker + Compose | 3.8 | Service orchestration |

## Directory Structure

```
fire-detection-monitoring/
├── docker-compose.yml          # Main orchestration file
├── run-all.sh                  # Master service management script
├── .env                        # Environment variables (Telegram tokens)
├── test_fire_alerts.py         # Comprehensive testing suite
│
├── exporter/                   # Custom Prometheus Exporter (Python)
│   ├── main.py                 # FastAPI application entry point
│   ├── mqtt_handler.py         # MQTT subscription and message handling
│   ├── metrics.py              # Prometheus metrics definitions
│   ├── notification.py         # Telegram notification service
│   ├── Dockerfile              # Container build instructions
│   └── requirements.txt        # Python dependencies
│
├── prometheus/                 # Prometheus Configuration
│   ├── prometheus.yml          # Scrape configuration
│   └── alerts.yml              # Alerting rules
│
├── alertmanager/               # Alertmanager Configuration
│   └── alertmanager.yml        # Routing and notification config
│
├── grafana/                    # Grafana Configuration
│   ├── grafana.ini             # Grafana settings
│   └── provisioning/
│       ├── datasources/        # Prometheus data source
│       └── dashboards/         # Pre-configured dashboards
│           └── fire-detection.json  # Geo-map dashboard
│
├── mosquitto/                  # MQTT Broker
│   ├── mosquitto.conf          # Broker configuration
│   └── run.sh                  # Service start script
│
├── nginx/                      # Image Server
│   ├── nginx.conf              # Web server configuration
│   └── run.sh                  # Service start script
│
├── images/                     # Fire detection images storage
└── test_images/                # Test images for simulation
```

## Core Components

### 1. MQTT Handler ([exporter/mqtt_handler.py](exporter/mqtt_handler.py))

Subscribes to wildfire MQTT topics and processes incoming messages:

**Topics:**
| Topic | Purpose |
|-------|---------|
| `wildfire/alerts` | Fire/smoke detection alerts with images |
| `wildfire/heartbeat` | Device health heartbeats |
| `wildfire/resolved` | Alert resolution notifications |
| `wildfire/devices/status` | Device status updates (battery, temp, uptime) |

**Key Functions:**
- `_handle_alert()` - Processes fire alerts, saves images, triggers notifications
- `_handle_heartbeat()` - Updates device online status
- `_handle_resolved()` - Removes resolved alerts from active monitoring
- `_handle_device_status()` - Tracks device health metrics

### 2. Metrics Module ([exporter/metrics.py](exporter/metrics.py))

Defines Prometheus metrics for Grafana visualization:

**Metrics:**
| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `fire_alert_info` | Gauge | alert_id, device_id, lat, lon, location, class | Active fire alerts (for Geomap) |
| `fire_confidence_latest` | Gauge | device_id, lat, lon, location | Latest detection confidence |
| `fire_device_status` | Gauge | device_id, lat, lon, location | Device online status (1/0) |
| `fire_device_battery` | Gauge | device_id, lat, lon, location | Battery percentage |
| `fire_device_temperature` | Gauge | device_id, lat, lon, location | Device temperature |
| `fire_alerts_total` | Counter | device_id, location, class | Total alerts count |
| `fire_active_alerts_count` | Gauge | - | Current active alerts |
| `fire_resolved_total` | Counter | resolution_type, resolved_by | Resolved alerts count |

### 3. Notification Service ([exporter/notification.py](exporter/notification.py))

Handles Telegram notifications with a dual-notification strategy:

1. **Immediate Notification** (via Exporter):
   - Sent instantly when fire detected
   - Includes photo attachment
   - Contains location coordinates with Google Maps link

2. **Reminder Notifications** (via Alertmanager):
   - Sent if alert not resolved after 15 minutes
   - Repeats every 15-30 minutes
   - Text-only reminders

### 4. REST API ([exporter/main.py](exporter/main.py))

FastAPI endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Service status |
| `/health` | GET | Health check (MQTT connection status) |
| `/metrics` | GET | Prometheus metrics scrape endpoint |
| `/alerts` | GET | List all active alerts (debugging) |
| `/test-alert` | POST | Generate test alert (development) |

### 5. Alerting Rules ([prometheus/alerts.yml](prometheus/alerts.yml))

| Alert | Condition | Severity |
|-------|-----------|----------|
| `FireDetected` | confidence > 50% | Critical |
| `HighConfidenceFire` | confidence > 90% | Critical |
| `DeviceOffline` | device offline > 5min | Warning |
| `MultipleFireAlerts` | > 5 alerts in 10min | Warning |

## Data Flow

### Fire Alert Flow

```
1. Edge Device detects fire/smoke
   ↓
2. Publishes to MQTT: wildfire/alerts
   {
     "alert_id": "alert_123",
     "device_id": "edge_device_001",
     "location": {"lat": 21.0285, "lon": 105.8542, "name": "Ba Vi Forest"},
     "confidence_max": 0.85,
     "detections": [{"class": "fire", "confidence": 0.85}],
     "image_base64": "..."
   }
   ↓
3. Exporter receives message
   ↓
4. Saves image to /app/images/{alert_id}.jpg
   ↓
5. Updates Prometheus metrics (fire_alert_info, etc.)
   ↓
6. Sends immediate Telegram notification with photo
   ↓
7. Prometheus scrapes metrics every 10s
   ↓
8. Grafana displays on Geomap dashboard
   ↓
9. If not resolved in 15min → Alertmanager sends reminder
```

### Resolution Flow

```
1. Operator sends resolution via MQTT: wildfire/resolved
   {
     "alert_id": "alert_123",
     "resolution_type": "extinguished",
     "resolved_by": "fire_response_team",
     "notes": "Fire contained and verified"
   }
   ↓
2. Exporter removes alert from active_alerts
   ↓
3. Prometheus metrics updated (alert disappears)
   ↓
4. Alertmanager stops sending reminders
   ↓
5. Telegram notification confirms resolution
```

## Network Configuration

All services communicate via shared Docker network: `fire-detection-network`

| Service | Container Name | Internal Host | Ports |
|---------|---------------|---------------|-------|
| Mosquitto | fire-mosquitto | mosquitto:1883 | 1883, 9001 |
| Exporter | fire-exporter | exporter:8000 | 8000 |
| Prometheus | fire-prometheus | prometheus:9090 | 9090 |
| Alertmanager | fire-alertmanager | alertmanager:9093 | 9093 |
| Grafana | fire-grafana | grafana:3000 | 3000 |
| Nginx | fire-nginx | nginx:80 | 8080 |

## Configuration

### Environment Variables

```bash
# .env file
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id  # Can be comma-separated for multiple
```

### Key Configuration Files

- **[docker-compose.yml](docker-compose.yml)** - Service definitions and volumes
- **[prometheus/prometheus.yml](prometheus/prometheus.yml)** - Scrape targets and intervals
- **[alertmanager/alertmanager.yml](alertmanager/alertmanager.yml)** - Alert routing rules
- **[mosquitto/mosquitto.conf](mosquitto/mosquitto.conf)** - MQTT broker settings

## Quick Start

```bash
# Start all services
./run-all.sh start all

# Check status
./run-all.sh status

# View logs
./run-all.sh logs exporter

# Stop all
./run-all.sh stop all
```

## Testing

```bash
# Single fire alert
python test_fire_alerts.py -t single

# Fire with resolution
python test_fire_alerts.py -t resolve

# Device status
python test_fire_alerts.py -t device_status --count 5

# Full test suite
python test_fire_alerts.py -t full -v
```

## Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / admin123 |
| Prometheus | http://localhost:9090 | - |
| Alertmanager | http://localhost:9093 | - |
| Exporter Metrics | http://localhost:8000/metrics | - |
| Image Server | http://localhost:8080/images/ | - |

## Grafana Dashboard Features

The pre-configured dashboard ([grafana/provisioning/dashboards/fire-detection.json](grafana/provisioning/dashboards/fire-detection.json)) includes:

- **Geomap Panel**: Real-time fire locations on Vietnam map
  - Color-coded by confidence level
  - Clickable markers with alert details
  - Device locations overlay
- **Statistics Panels**: Active alerts, device status, total counts
- **Timeline**: Alert history and trends

## Supported Detection Classes

| Class | Description |
|-------|-------------|
| `fire` | Active fire detection |
| `smoke` | Smoke detection (early warning) |

## Vietnam Forest Locations

The system is pre-configured with 15 major forest locations across Vietnam:
- **Northern**: Hoang Lien (Sa Pa), Ba Vi, Tam Dao, Cat Ba, Soc Son
- **Central**: Bach Ma, Phong Dien, Kon Ka Kinh, Bidoup Nui Ba, Phong Nha
- **Southern**: Cat Tien, Can Gio Mangrove, U Minh Thuong, Binh Chau, Da Lat Pine

## Dependencies

### Python (exporter)
```
prometheus_client==0.19.0
paho-mqtt==1.6.1
fastapi==0.109.0
uvicorn==0.25.0
requests==2.31.0
Pillow==10.2.0
aiohttp==3.9.1
python-dotenv==1.0.0
```

### System
- Docker 20.10+
- Docker Compose 2.x
- Python 3.11+ (for testing scripts)
