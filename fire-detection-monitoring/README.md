# Fire Detection Monitoring System

Hệ thống giám sát phát hiện cháy rừng sử dụng Grafana Geomap và Prometheus.

## Kiến Trúc

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Mosquitto    │────▶│    Exporter     │────▶│   Prometheus    │
│   (MQTT Broker) │     │ (Metrics + MQTT)│     │   (Time-series) │
│   Port: 1883    │     │   Port: 8000    │     │   Port: 9090    │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                │                        │
                                ▼                        ▼
                        ┌───────────────┐       ┌─────────────────┐
                        │     Nginx     │       │     Grafana     │
                        │ (Image Server)│       │   (Dashboard)   │
                        │  Port: 8080   │       │   Port: 3000    │
                        └───────────────┘       └─────────────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │  Alertmanager   │
                                                │   (Telegram)    │
                                                │   Port: 9093    │
                                                └─────────────────┘
```

## Quick Start

### Chạy tất cả services

```bash
# Cấp quyền thực thi
chmod +x run-all.sh
chmod +x */run.sh

# Start tất cả
./run-all.sh start all

# Kiểm tra status
./run-all.sh status
```

### Chạy từng service độc lập

```bash
# 1. Start MQTT Broker (bắt buộc đầu tiên)
./mosquitto/run.sh start

# 2. Start Nginx (image server)
./nginx/run.sh start

# 3. Start Exporter
./exporter/run.sh start

# 4. Start Prometheus
./prometheus/run.sh start

# 5. Start Alertmanager
./alertmanager/run.sh start

# 6. Start Grafana
./grafana/run.sh start
```

## Services

| Service | Port | URL | Mô tả |
|---------|------|-----|-------|
| **Mosquitto** | 1883, 9001 | - | MQTT Broker |
| **Nginx** | 8080 | http://localhost:8080/images/ | Image server |
| **Exporter** | 8000 | http://localhost:8000/metrics | Prometheus exporter |
| **Prometheus** | 9090 | http://localhost:9090 | Metrics storage |
| **Alertmanager** | 9093 | http://localhost:9093 | Alert notifications |
| **Grafana** | 3000 | http://localhost:3000 | Dashboard (admin/admin123) |

## Cấu Trúc Thư Mục

```
fire-detection-monitoring/
├── .env                     # Environment variables (Telegram tokens)
├── docker-compose.yml       # Docker Compose (chạy tất cả cùng lúc)
├── run-all.sh              # Master script quản lý services
├── images/                 # Thư mục lưu ảnh từ alerts
│
├── mosquitto/
│   ├── Dockerfile
│   ├── mosquitto.conf
│   └── run.sh
│
├── exporter/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── metrics.py
│   ├── mqtt_handler.py
│   ├── notification.py
│   └── run.sh
│
├── prometheus/
│   ├── Dockerfile
│   ├── prometheus.yml
│   ├── alerts.yml
│   ├── entrypoint.sh
│   └── run.sh
│
├── alertmanager/
│   ├── Dockerfile
│   ├── alertmanager.yml
│   ├── entrypoint.sh
│   └── run.sh
│
├── grafana/
│   ├── Dockerfile
│   ├── grafana.ini
│   ├── entrypoint.sh
│   ├── run.sh
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yml
│       └── dashboards/
│           ├── dashboard.yml
│           └── fire-detection.json
│
└── nginx/
    ├── Dockerfile
    ├── nginx.conf
    └── run.sh
```

## Commands

### Master Script (run-all.sh)

```bash
./run-all.sh start all       # Start tất cả services
./run-all.sh stop all        # Stop tất cả services
./run-all.sh restart all     # Restart tất cả services
./run-all.sh status          # Kiểm tra status
./run-all.sh logs exporter   # Xem logs của exporter
./run-all.sh build all       # Build lại tất cả images
./run-all.sh clean           # Xóa tất cả containers và images
```

### Từng Service

```bash
# Mỗi service có script run.sh riêng
./<service>/run.sh build     # Build Docker image
./<service>/run.sh start     # Start container
./<service>/run.sh stop      # Stop container
./<service>/run.sh logs      # Xem logs
./<service>/run.sh status    # Kiểm tra status
```

### Exporter Commands (đặc biệt)

```bash
./exporter/run.sh start-local  # Chạy local không cần Docker (debug)
./exporter/run.sh test         # Gửi test alert
./exporter/run.sh shell        # Mở shell trong container
```

### Alertmanager Commands (đặc biệt)

```bash
./alertmanager/run.sh test-alert  # Gửi test alert đến Telegram
```

## Cấu Hình

### Environment Variables (.env)

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Thay đổi targets (khi chạy độc lập)

```bash
# Exporter - kết nối đến MQTT trên host
MQTT_BROKER=host.docker.internal ./exporter/run.sh start

# Prometheus - kết nối đến Exporter trên host
EXPORTER_TARGET=host.docker.internal:8000 ./prometheus/run.sh start

# Grafana - kết nối đến Prometheus trên host
PROMETHEUS_URL=http://host.docker.internal:9090 ./grafana/run.sh start
```

## Testing

### 1. Test MQTT

```bash
# Subscribe
mosquitto_sub -h localhost -t 'wildfire/#' -v

# Publish test message
mosquitto_pub -h localhost -t wildfire/test -m "hello"
```

### 2. Test Exporter

```bash
# Health check
curl http://localhost:8000/health

# View metrics
curl http://localhost:8000/metrics

# Send test alert
curl -X POST http://localhost:8000/test-alert

# View active alerts
curl http://localhost:8000/alerts
```

### 3. Test Prometheus

```bash
# Query metrics
curl 'http://localhost:9090/api/v1/query?query=fire_alert_info'

# Check targets
curl http://localhost:9090/api/v1/targets
```

### 4. Test Alertmanager

```bash
# Send test alert
./alertmanager/run.sh test-alert

# View active alerts
curl http://localhost:9093/api/v2/alerts
```

### 5. Test Full Flow (MQTT → Exporter → Prometheus)

```bash
# Send fire alert via MQTT
mosquitto_pub -h localhost -t wildfire/alerts -m '{
  "alert_id": "test_001",
  "device_id": "edge_device_001",
  "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
  "location": {
    "lat": 21.0285,
    "lon": 105.8542,
    "name": "Test Location"
  },
  "detections": [
    {"class": "fire", "confidence": 0.92}
  ],
  "confidence_max": 0.92
}'

# Verify in Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=fire_alert_info' | python -m json.tool
```

## Debugging

### Xem logs của từng service

```bash
./run-all.sh logs mosquitto
./run-all.sh logs exporter
./run-all.sh logs prometheus
./run-all.sh logs alertmanager
./run-all.sh logs grafana
```

### Chạy Exporter local (không Docker)

```bash
cd exporter
pip install -r requirements.txt
export MQTT_BROKER=localhost
python main.py
```

### Reset Grafana password

```bash
./grafana/run.sh reset-password newpassword
```

## Troubleshooting

### 1. Exporter không kết nối được MQTT

```bash
# Kiểm tra Mosquitto đang chạy
docker ps | grep mosquitto

# Kiểm tra logs
./mosquitto/run.sh logs

# Test kết nối
mosquitto_pub -h localhost -t test -m "hello"
```

### 2. Prometheus không scrape được Exporter

```bash
# Kiểm tra target
curl http://localhost:9090/api/v1/targets

# Kiểm tra exporter đang chạy
curl http://localhost:8000/health

# Nếu chạy độc lập, cần dùng host.docker.internal
EXPORTER_TARGET=host.docker.internal:8000 ./prometheus/run.sh start
```

### 3. Grafana không hiển thị data

1. Kiểm tra datasource: Settings → Data sources → Prometheus → Test
2. Kiểm tra Prometheus có data: http://localhost:9090 → Query `fire_alert_info`
3. Kiểm tra panel query trong Grafana

### 4. Telegram notification không gửi

```bash
# Kiểm tra .env file
cat .env

# Test trực tiếp
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d "chat_id=<CHAT_ID>" \
  -d "text=Test"

# Kiểm tra Alertmanager logs
./alertmanager/run.sh logs
```

## Chạy với Docker Compose (Alternative)

Nếu muốn chạy tất cả cùng lúc với Docker Compose:

```bash
docker-compose up -d
docker-compose logs -f
docker-compose down
```
