# Thiết kế hệ thống — Phát hiện cháy rừng thời gian thực trên Edge AI + k3s

## 1. Tổng quan kiến trúc

Hệ thống triển khai trên cụm **k3s multi-node**: một master node trên cloud và các edge node (đại diện cho thiết bị nhỏ như Raspberry Pi). Tất cả thành phần được đóng gói thành Kubernetes workload.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLOUD (master node)                          │
│                                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────┐ │
│  │ Grafana   │  │ Prometheus   │  │ Model      │  │ MQTT Broker  │ │
│  │ (Geomap)  │  │              │  │ Server     │  │ (Mosquitto)  │ │
│  │ :3000     │  │ :9090        │  │ :8000      │  │ :1883        │ │
│  └─────┬─────┘  └──────┬───────┘  └──────┬─────┘  └──────┬───────┘ │
│        │               │                 │                │         │
│        │  ◄── scrape ──┘                 │                │         │
│        │                                 │                │         │
└────────┼─────────────────────────────────┼────────────────┼─────────┘
         │                                 │                │
    k3s control plane                      │                │
         │                                 │                │
┌────────┼─────────────────────────────────┼────────────────┼─────────┐
│        │          EDGE NODE(s)           │                │         │
│        │                                 │                │         │
│  ┌─────┴──────────────────┐   ┌──────────┴─────┐         │         │
│  │ Inference Pod (HPA)    │   │ Init Container │         │         │
│  │ ┌───────────────────┐  │   │ pulls latest   │         │         │
│  │ │ MQTT-Bridge       │◄─┼───┤ model from     │         │         │
│  │ │ (Python :9090)    │  │   │ Model Server   │         │         │
│  │ │  - subscribe MQTT │  │   └────────────────┘         │         │
│  │ │  - send to C++    │  │                              │         │
│  │ │  - export metrics │  │                              │         │
│  │ └────────┬──────────┘  │                              │         │
│  │          │ localhost    │                              │         │
│  │ ┌────────▼──────────┐  │                              │         │
│  │ │ C++ Backend       │  │                              │         │
│  │ │ (ONNX Runtime     │  │                              │         │
│  │ │  :8080)           │  │                              │         │
│  │ └──────────────────┘  │                              │         │
│  └────────────────────────┘                              │         │
│                                                          │         │
│  ┌────────────────────────────────────────┐              │         │
│  │ Frame Extractor Pod                    │              │         │
│  │  - reads video files                   ├──────────────┘         │
│  │  - extracts frames at interval         │   publish to MQTT      │
│  │  - attaches location (lat/lon) + ID    │   topic: frames/<loc>  │
│  │  - publishes raw RGB to MQTT           │                        │
│  └────────────────────────────────────────┘                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Cụm k3s multi-node

### Master node (cloud)

- Chạy k3s server (control plane).
- Chứa các workload nhẹ: MQTT broker, Model Server, Prometheus, Grafana.
- Label: `node-role=cloud`.

### Edge node(s)

- Chạy k3s agent, join vào master.
- Thiết bị nhỏ (Raspberry Pi hoặc tương đương).
- Chạy workload nặng tính toán: Inference Pod, Frame Extractor.
- Label: `node-role=edge`.

### Cài đặt

```bash
# Master (cloud):
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
  --write-kubeconfig-mode 644 \
  --tls-san <MASTER_IP> \
  --node-label node-role=cloud" sh -

# Edge node:
curl -sfL https://get.k3s.io | K3S_URL="https://<MASTER_IP>:6443" \
  K3S_TOKEN="<TOKEN>" \
  INSTALL_K3S_EXEC="agent --node-label node-role=edge" sh -
```

Các workload sử dụng `nodeSelector` để đảm bảo schedule đúng node:

| Workload | nodeSelector |
|----------|-------------|
| MQTT Broker, Model Server, Prometheus, Grafana | `node-role: cloud` |
| Inference Pod, Frame Extractor | `node-role: edge` |

---

## 3. Luồng dữ liệu

```
Video files ──► Frame Extractor ──► MQTT Broker ──► Inference Pod ──► Prometheus ──► Grafana
  (camera         (extract 224x224    (Mosquitto       (detect fire,      (scrape       (Geomap
   simulation)     + GPS metadata)     :1883)           export metrics)    :9090)        panel)
```

**Chi tiết từng bước:**

1. **Frame Extractor** đọc video (mô phỏng camera tại vị trí GPS), trích frame 224×224, gắn metadata `{location_id, lat, lon}`, publish lên MQTT topic `frames/<location_id>`.

2. **MQTT Broker** (Mosquitto) nhận và phân phối frame tới tất cả subscriber.

3. **Inference Pod** (auto-scale bằng HPA):
   - Container **mqtt-bridge** (Python) subscribe `frames/#`, nhận frame + metadata.
   - Gửi frame tới container **fire-backend** (C++ ONNX Runtime) qua `localhost:8080/predict`.
   - Nhận kết quả JSON `{class, confidence}`, export Prometheus metrics kèm label `location`, `lat`, `lon`.

4. **Prometheus** scrape metrics từ mqtt-bridge (`:9090`) qua pod annotation discovery.

5. **Grafana** hiển thị Geomap panel (bản đồ) theo tọa độ, màu sắc phản ánh mức confidence (xanh → vàng → cam → đỏ).

---

## 4. Các thành phần chi tiết

### 4.1 MQTT Broker

| Thuộc tính | Giá trị |
|-----------|---------|
| Image | `eclipse-mosquitto:2` |
| Port | `1883` |
| Node | Cloud |
| Max message size | 1 MB |

MQTT topic schema:

| Topic | Nội dung |
|-------|---------|
| `frames/<location_id>` | Raw 224×224×3 bytes (150528 B) |
| `frames/<location_id>/meta` | JSON `{id, lat, lon, file}` (retained) |

### 4.2 Model Server

Flask HTTP server trên cloud node, phục vụ file ONNX model.

| Endpoint | Chức năng |
|----------|----------|
| `GET /model` | Tải file `fire_detection.onnx` |
| `GET /version` | MD5 hash của model (dùng để so sánh version) |
| `GET /health` | Health check |

Model được lưu tại `hostPath: /opt/fire-detection/models/` trên cloud node. Khi huấn luyện xong model mới, chỉ cần copy file ONNX vào thư mục này.

### 4.3 Model Sync (tự động phân phối model mới)

**Cơ chế:**

```
Model Server (/version) ──► CronJob (mỗi 5 phút) ──► So sánh MD5
                                                           │
                                                     Nếu khác:
                                                           │
                                                     ┌─────▼──────┐
                                                     │ Update CM   │
                                                     │ model-ver   │
                                                     └─────┬──────┘
                                                           │
                                                     ┌─────▼──────────────┐
                                                     │ Rolling restart     │
                                                     │ inference deploy    │
                                                     └─────┬──────────────┘
                                                           │
                                                     ┌─────▼──────────────┐
                                                     │ Init container      │
                                                     │ wget model mới      │
                                                     └────────────────────┘
```

- **CronJob `model-sync`** chạy mỗi 5 phút trên cloud node.
- So sánh MD5 từ Model Server với ConfigMap `model-version`.
- Nếu khác → cập nhật ConfigMap + `kubectl rollout restart deployment/inference`.
- Inference Pod có **init container** (`busybox:1.36`) tải model mới nhất từ Model Server vào shared `emptyDir` volume.
- RBAC: ServiceAccount `model-sync` được cấp quyền get/patch ConfigMap và Deployment trong namespace `fire-detection`.

### 4.4 Frame Extractor

Mô phỏng camera feed bằng cách đọc video file và trích frame.

**Cấu hình camera (ConfigMap `frame-sources`):**

```json
[
  {
    "id": "cam-binhphuoc-01",
    "file": "Forest Fire with Drone Support.mp4",
    "lat": 11.75,
    "lon": 106.90,
    "description": "Binh Phuoc forest area"
  },
  {
    "id": "cam-dalat-01",
    "file": "Heilbronn Germany _ Foggy Forest _ Cinematic Drone Video.mp4",
    "lat": 11.94,
    "lon": 108.44,
    "description": "Da Lat pine forest"
  }
]
```

**Xử lý:**

1. Đọc `sources.json` từ ConfigMap.
2. Mỗi nguồn video chạy trên một thread riêng.
3. Mỗi frame: resize 224×224 RGB → `tobytes()` (150528 B) → publish MQTT.
4. Khi hết video → loop lại từ đầu (stream liên tục).
5. Metadata (lat/lon) được publish retained trên topic `frames/<id>/meta`.

Video files mount từ `hostPath: /opt/fire-detection/videos/` trên edge node.

### 4.5 Inference Pod (Sidecar pattern)

Mỗi pod gồm 3 phần:

| Container | Image | Vai trò | Port |
|-----------|-------|---------|------|
| `model-init` (init) | `busybox:1.36` | Tải ONNX model từ Model Server | — |
| `mqtt-bridge` (sidecar) | `fire-mqtt-bridge` | Subscribe MQTT, gửi tới C++, export metrics | 9090 |
| `fire-backend` (main) | `fire-backend` | ONNX Runtime inference (C++) | 8080 |

**mqtt-bridge flow:**

```
MQTT frames/#  ──►  bridge.py  ──►  POST localhost:8080/predict  ──►  JSON result
                        │                                                  │
                        │              Prometheus metrics ◄────────────────┘
                        │              (fire_detection_total,
                        │               fire_detection_confidence,
                        │               fire_detection_latency_seconds)
                        │
                        └──►  if class=="fire": log alert
```

**Prometheus metrics:**

| Metric | Type | Labels | Mô tả |
|--------|------|--------|--------|
| `fire_detection_total` | Counter | `location`, `result` | Tổng số lần inference |
| `fire_detection_confidence` | Gauge | `location`, `lat`, `lon` | Confidence mới nhất |
| `fire_detection_latency_seconds` | Histogram | `location` | Độ trễ inference |

Label `lat` và `lon` trên `fire_detection_confidence` cho phép Grafana Geomap hiển thị trên bản đồ.

### 4.6 Auto-scaling (HPA)

```yaml
minReplicas: 1
maxReplicas: 5
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

Khi CPU utilization trung bình vượt 70%, HPA tự động scale thêm inference pod. Mỗi pod mới sẽ:
- Init container tải model từ Model Server.
- Subscribe MQTT (Mosquitto load-balance giữa subscriber cùng topic).

### 4.7 Monitoring: Prometheus + Grafana

**Prometheus** scrape inference pods qua pod annotation discovery:
- `prometheus.io/scrape: "true"`
- `prometheus.io/port: "9090"`

**Grafana dashboard** gồm 5 panel:

| Panel | Type | Query |
|-------|------|-------|
| Fire Detection Map | **Geomap** | `fire_detection_confidence` (table, instant) → lat/lon fields |
| Detection Rate | Timeseries | `rate(fire_detection_total{result="fire"}[1m])` |
| Inference Latency (p95) | Timeseries | `histogram_quantile(0.95, rate(fire_detection_latency_seconds_bucket[5m]))` |
| Total Detections | Stat | `sum(fire_detection_total{result="fire"})` |
| Active Locations | Stat | `count(fire_detection_confidence)` |

**Geomap color thresholds:**

| Confidence | Màu |
|-----------|------|
| < 0.5 | Xanh lá (bình thường) |
| 0.5 – 0.7 | Vàng (cảnh báo) |
| 0.7 – 0.8 | Cam (nguy hiểm) |
| > 0.8 | Đỏ (cháy) |

Cài đặt qua Helm:
- `prometheus-community/prometheus` (chỉ bật server, tắt alertmanager/node-exporter/pushgateway).
- `grafana/grafana` (NodePort 30300, mật khẩu mặc định: `fire-admin`).

---

## 5. Cấu trúc thư mục `deploy/`

```
deploy/
├── README.md                          # Hướng dẫn triển khai nhanh
├── namespace.yaml                     # Namespace fire-detection
│
├── k3s/
│   ├── install-master.sh              # Cài k3s server (cloud)
│   └── join-edge.sh                   # Join edge node vào cluster
│
├── mqtt/
│   ├── deployment.yaml                # Mosquitto broker + ConfigMap
│   └── service.yaml                   # ClusterIP :1883
│
├── model-server/
│   ├── Dockerfile                     # Flask HTTP server image
│   ├── server.py                      # /model, /version, /health
│   └── deployment.yaml                # Deployment + Service (cloud)
│
├── model-sync/
│   └── cronjob.yaml                   # CronJob + RBAC (check & restart)
│
├── frame-extractor/
│   ├── Dockerfile                     # Python OpenCV + paho-mqtt
│   ├── extractor.py                   # Đọc video → frame → MQTT
│   ├── configmap.yaml                 # sources.json (video → GPS)
│   └── deployment.yaml                # Deployment (edge node)
│
├── inference/
│   ├── Dockerfile.bridge              # Python MQTT bridge image
│   ├── bridge.py                      # MQTT → C++ → Prometheus
│   ├── deployment.yaml                # Sidecar: bridge + backend + init
│   ├── service.yaml                   # :8080 + :9090
│   └── hpa.yaml                       # HPA 1–5 replicas, CPU 70%
│
└── monitoring/
    ├── install.sh                     # Helm install Prometheus + Grafana
    ├── prometheus-values.yaml         # Pod annotation scrape config
    └── grafana-dashboard.json         # Geomap + timeseries + stats
```

---

## 6. Resource budget (ước tính cho edge node nhỏ — 2 GB RAM, 4 vCPU)

| Pod | CPU request | CPU limit | Memory request | Memory limit |
|-----|-------------|-----------|----------------|-------------|
| Frame Extractor | — | 500m | — | 512 Mi |
| Inference (bridge) | 100m | 300m | 128 Mi | 256 Mi |
| Inference (backend) | 250m | 1000m | 256 Mi | 512 Mi |
| **Tổng (1 inference replica)** | **350m** | **1800m** | **384 Mi** | **1280 Mi** |

Với edge node 2 GB RAM, có thể chạy thoải mái 1 inference replica + 1 frame extractor. HPA scale thêm replica khi có nhiều edge node hơn.

---

## 7. Quyết định thiết kế

| Quyết định | Lý do |
|-----------|-------|
| **Sidecar pattern** (bridge + backend) | Python xử lý I/O (MQTT, metrics) tốt; C++ xử lý inference nhanh. Tách riêng để scale và debug độc lập. |
| **MQTT** thay vì HTTP push | Pub/sub pattern phù hợp với nhiều camera + nhiều consumer. Mosquitto rất nhẹ. |
| **Init container** tải model | Đảm bảo pod luôn có model trước khi start. Không cần persistent volume. |
| **CronJob** sync model | Đơn giản, không cần webhook/operator phức tạp. 5 phút delay chấp nhận được. |
| **Pod annotation** cho Prometheus | Không cần ServiceMonitor CRD, tương thích với Prometheus Helm chart mặc định. |
| **Grafana Geomap** | Sử dụng label `lat`, `lon` trên metric, không cần GeoJSON hay database riêng. |
| **hostPath** cho video/model | Đơn giản nhất cho edge node đơn lẻ. Production có thể chuyển sang NFS/S3. |
