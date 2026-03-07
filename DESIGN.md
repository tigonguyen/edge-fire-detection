# Thiết kế hệ thống — Phát hiện cháy rừng thời gian thực trên Edge AI + k3s

## 1. Tổng quan kiến trúc

Hệ thống chia thành **3 tầng** (devices → edge → cloud), triển khai trên cụm k3s multi-node.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           CLOUD (master node)                            │
│                           node-role: cloud                               │
│                                                                          │
│  ┌───────────┐   ┌──────────────┐   ┌──────────────┐   ┌─────────────┐ │
│  │ Grafana    │   │ Prometheus   │   │ Model Server │   │ Model Sync  │ │
│  │ (Geomap)  │   │              │   │ (Flask)      │   │ (CronJob)   │ │
│  │ :30300    │   │ :9090        │   │ :8000        │   │ */5 min     │ │
│  └─────┬─────┘   └──────┬───────┘   └──────┬───────┘   └──────┬──────┘ │
│        │                │                   │                  │         │
│        │  ◄── scrape ───┘                   │         check version     │
│        │                                    │         & rolling restart  │
└────────┼────────────────────────────────────┼──────────────────┼────────┘
         │                                    │                  │
    k3s control plane                         │                  │
         │                                    │                  │
┌────────┼────────────────────────────────────┼──────────────────┼────────┐
│        │               EDGE NODE(s)         │                  │         │
│        │               node-role: edge      │                  │         │
│        │                                    │                  │         │
│  ┌─────┴──────────────────────────┐  ┌──────┴───────┐         │         │
│  │ Inference Pod (HPA: 1–5)       │  │ Init Cont.   │         │         │
│  │                                │  │ wget model   │◄────────┘         │
│  │  ┌──────────────────────────┐  │  │ from cloud   │                   │
│  │  │ inference.py             │  │  └──────────────┘                   │
│  │  │  (Python single process) │  │                                     │
│  │  │                          │  │                                     │
│  │  │  MQTT subscribe frames/# │  │                                     │
│  │  │  ONNX Runtime inference  │  │                                     │
│  │  │  Prometheus metrics:9090 │  │                                     │
│  │  └──────────────────────────┘  │                                     │
│  └────────────────────────────────┘                                     │
│                                                                          │
│  ┌────────────────────────────────┐                                     │
│  │ MQTT Broker (Mosquitto)        │                                     │
│  │ :1883                          │◄──── subscribe ─── Inference Pod    │
│  └──────────┬─────────────────────┘                                     │
│             │                                                            │
└─────────────┼────────────────────────────────────────────────────────────┘
              │ publish frames
              │
┌─────────────┼────────────────────────────────────────────────────────────┐
│             │          DEVICE NODE(s)                                     │
│             │          node-role: device                                  │
│                                                                          │
│  ┌──────────┴─────────────────────────────────────┐                     │
│  │ Frame Extractor Pod                             │                     │
│  │  - reads video files (simulate cameras)         │                     │
│  │  - extracts 224×224 RGB frames                  │                     │
│  │  - attaches location metadata (lat/lon/ID)      │                     │
│  │  - publishes to MQTT topic: frames/<location>   │                     │
│  └─────────────────────────────────────────────────┘                     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Ba tầng hệ thống

### 2.1 Devices (node-role: device)

Tầng thu thập dữ liệu. Mỗi device node mô phỏng một hoặc nhiều camera giám sát rừng.

| Thành phần | Chức năng |
|-----------|----------|
| Frame Extractor | Đọc video file, trích frame 224×224 RGB, gắn GPS metadata, publish lên MQTT |

- Mỗi nguồn video (camera) chạy trên một thread riêng.
- Frame được publish dưới dạng raw bytes (150528 B) lên topic `frames/<location_id>`.
- Metadata `{id, lat, lon}` được publish retained lên `frames/<location_id>/meta`.
- Video loop liên tục khi hết file (mô phỏng stream thời gian thực).

### 2.2 Edge (node-role: edge)

Tầng xử lý. Nhận frame từ devices qua MQTT, chạy AI inference, xuất metrics.

| Thành phần | Chức năng |
|-----------|----------|
| MQTT Broker (Mosquitto) | Nhận frame từ devices, phân phối tới inference pods |
| Inference App (Python + ONNX Runtime) | Subscribe MQTT → inference → export Prometheus metrics |

**MQTT Broker** nằm trên edge (gần inference) để giảm latency giữa broker và consumer.

**Inference App** là một process Python duy nhất, tích hợp 3 chức năng:
1. **MQTT client** — subscribe `frames/#`, nhận frame + metadata từ broker.
2. **ONNX Runtime** — load model `fire_detection.onnx`, preprocess (normalize ImageNet), chạy inference.
3. **prometheus_client** — export metrics trực tiếp trên port `:9090`.

Không cần sidecar hay C++ riêng — một container duy nhất xử lý toàn bộ.

### 2.3 Cloud (node-role: cloud)

Tầng quản lý và giám sát. Chạy trên master node.

| Thành phần | Chức năng |
|-----------|----------|
| Model Server (Flask) | Phục vụ ONNX model qua HTTP (`/model`, `/version`, `/health`) |
| Model Sync (CronJob) | Kiểm tra version mỗi 5 phút, rolling restart inference nếu có model mới |
| Prometheus | Scrape metrics từ inference pods trên edge |
| Grafana | Hiển thị Geomap (bản đồ cháy) + dashboard metrics |

---

## 3. Luồng dữ liệu

```
  DEVICES                    EDGE                           CLOUD
 ─────────              ─────────────                  ──────────────

 Video files            MQTT Broker                    Prometheus
     │                      │                              │
     ▼                      │                              │
 Frame Extractor ──publish──► :1883 ◄──subscribe── Inference Pod ──► :9090
     │                                                 │       │
     │ frames/<loc_id>                                 │       │
     │ + /meta (retained)                        ONNX Runtime  │
     │                                           inference     │
     │                                                 │       │
     │                                          fire/normal    │
     │                                          + confidence   │
     │                                                 │       │
     │                                                 ▼       │
     │                                          Prometheus ◄───┘
     │                                          metrics:
     │                                           • fire_detection_total
     │                                           • fire_detection_confidence
     │                                           • fire_detection_latency_seconds
     │                                                 │
     │                                                 ▼
     │                                             Grafana
     │                                             Geomap panel
     │                                             (lat/lon → bản đồ)
```

**Chi tiết từng bước:**

1. **Frame Extractor** (devices) đọc video, trích frame 224×224 RGB, publish `frames/<location_id>` + metadata retained.
2. **MQTT Broker** (edge) nhận và phân phối frame.
3. **Inference App** (edge) subscribe `frames/#`:
   - Nhận raw bytes → reshape → normalize (ImageNet mean/std) → ONNX Runtime inference.
   - Kết quả: `{class: fire|normal, confidence: 0.0–1.0}`.
   - Export Prometheus metrics với label `location`, `lat`, `lon`.
4. **Prometheus** (cloud) scrape metrics từ inference pods qua pod annotation discovery.
5. **Grafana** (cloud) hiển thị Geomap panel theo tọa độ GPS.

---

## 4. Các thành phần chi tiết

### 4.1 Frame Extractor (devices)

**Cấu hình camera — ConfigMap `frame-sources`:**

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

| Thuộc tính | Giá trị |
|-----------|---------|
| Image | `fire-frame-extractor` (Python 3.11 + OpenCV + paho-mqtt) |
| Node | `node-role: device` |
| MQTT topic | `frames/<location_id>` (raw 224×224×3 = 150528 bytes) |
| Interval | 2 giây/frame (cấu hình qua env `FRAME_INTERVAL`) |

### 4.2 MQTT Broker (edge)

| Thuộc tính | Giá trị |
|-----------|---------|
| Image | `eclipse-mosquitto:2` |
| Port | `1883` |
| Node | `node-role: edge` |
| Max message | 1 MB |

MQTT topic schema:

| Topic | Payload | Publisher | Subscriber |
|-------|---------|-----------|------------|
| `frames/<location_id>` | Raw 224×224×3 bytes | Frame Extractor | Inference App |
| `frames/<location_id>/meta` | JSON `{id, lat, lon}` (retained) | Frame Extractor | Inference App |

### 4.3 Inference App (edge)

Một container Python duy nhất tích hợp MQTT + ONNX + Prometheus.

| Thuộc tính | Giá trị |
|-----------|---------|
| Image | `fire-inference` (Python 3.11 + onnxruntime + paho-mqtt + prometheus_client) |
| Node | `node-role: edge` |
| Metrics port | `:9090` |
| Model path | `/model/fire_detection.onnx` (từ init container) |

**Inference pipeline:**

```
raw bytes (150528) → reshape(224,224,3) → float32/255 → normalize(ImageNet) → NCHW → ONNX → softmax → class + confidence
```

**Prometheus metrics xuất trực tiếp từ inference app:**

| Metric | Type | Labels | Mô tả |
|--------|------|--------|--------|
| `fire_detection_total` | Counter | `location`, `result` | Tổng số lần inference |
| `fire_detection_confidence` | Gauge | `location`, `lat`, `lon` | Confidence mới nhất |
| `fire_detection_latency_seconds` | Histogram | `location` | Độ trễ inference (seconds) |

Label `lat` và `lon` trên gauge `fire_detection_confidence` là key cho Grafana Geomap.

### 4.4 Model Server (cloud)

| Endpoint | Chức năng |
|----------|----------|
| `GET /model` | Tải file `fire_detection.onnx` |
| `GET /version` | MD5 hash (so sánh version) |
| `GET /health` | Health check |

Model lưu tại `hostPath: /opt/fire-detection/models/` trên cloud node.

### 4.5 Model Sync — tự động phân phối model mới (cloud)

```
Model Server (/version)
        │
   CronJob (*/5 min)
        │
   So sánh MD5 với ConfigMap model-version
        │
   Nếu khác ──► kubectl rollout restart deployment/inference
        │
   Init container trong inference pod ──► wget model mới từ Model Server
```

- CronJob chạy trên cloud node, dùng `bitnami/kubectl`.
- RBAC: ServiceAccount `model-sync` có quyền get/patch ConfigMap + Deployment.

### 4.6 Auto-scaling (HPA)

```yaml
minReplicas: 1
maxReplicas: 5
metrics:
  - resource: cpu
    target: averageUtilization 70%
```

Khi CPU vượt 70%, HPA scale thêm inference pod. Mỗi pod mới tự tải model (init container) và subscribe MQTT.

### 4.7 Monitoring — Prometheus + Grafana (cloud)

**Prometheus** scrape inference pods qua pod annotation:
- `prometheus.io/scrape: "true"`
- `prometheus.io/port: "9090"`

**Grafana dashboard** (6 panels):

| Panel | Type | Query |
|-------|------|-------|
| Fire Detection Map | **Geomap** | `fire_detection_confidence` → lat/lon fields |
| Detection Rate | Timeseries | `rate(fire_detection_total{result="fire"}[1m])` |
| Inference Latency p95 | Timeseries | `histogram_quantile(0.95, rate(..._bucket[5m]))` |
| Total Fire Alerts | Stat | `sum(fire_detection_total{result="fire"})` |
| Active Locations | Stat | `count(fire_detection_confidence)` |
| Inference Pods | Stat | `count(up{job="fire-detection"})` |

**Geomap color thresholds:**

| Confidence | Màu |
|-----------|------|
| < 0.5 | Xanh lá (bình thường) |
| 0.5 – 0.7 | Vàng (cảnh báo) |
| 0.7 – 0.8 | Cam (nguy hiểm) |
| > 0.8 | Đỏ (cháy) |

---

## 5. Cụm k3s multi-node

### Node labels

| Label | Vai trò | Ví dụ thiết bị |
|-------|---------|----------------|
| `node-role=cloud` | Master + monitoring + model server | Cloud VM |
| `node-role=edge` | MQTT + inference | Raspberry Pi |
| `node-role=device` | Frame extractor (camera simulation) | Raspberry Pi / IoT device |

### Cài đặt

```bash
# Cloud master:
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
  --write-kubeconfig-mode 644 \
  --tls-san <MASTER_IP> \
  --node-label node-role=cloud" sh -

# Edge node:
curl -sfL https://get.k3s.io | K3S_URL="https://<MASTER_IP>:6443" \
  K3S_TOKEN="<TOKEN>" \
  INSTALL_K3S_EXEC="agent --node-label node-role=edge" sh -

# Device node:
curl -sfL https://get.k3s.io | K3S_URL="https://<MASTER_IP>:6443" \
  K3S_TOKEN="<TOKEN>" \
  INSTALL_K3S_EXEC="agent --node-label node-role=device" sh -
```

### Workload → Node mapping

| Workload | Tầng | nodeSelector |
|----------|------|-------------|
| Frame Extractor | devices | `node-role: device` |
| MQTT Broker | edge | `node-role: edge` |
| Inference App | edge | `node-role: edge` |
| Model Server | cloud | `node-role: cloud` |
| Model Sync | cloud | `node-role: cloud` |
| Prometheus | cloud | `node-role: cloud` |
| Grafana | cloud | `node-role: cloud` |

---

## 6. Cấu trúc thư mục `deploy/`

```
deploy/
├── README.md                                    # Hướng dẫn triển khai nhanh
├── namespace.yaml                               # Namespace fire-detection
│
├── k3s/
│   ├── install-master.sh                        # Cài k3s server (cloud)
│   └── join-edge.sh                             # Join edge/device node
│
├── devices/
│   └── frame-extractor/
│       ├── Dockerfile                           # Python OpenCV + paho-mqtt
│       ├── extractor.py                         # Đọc video → frame → MQTT
│       ├── configmap.yaml                       # sources.json (video → GPS)
│       └── deployment.yaml                      # Deployment (device node)
│
├── edge/
│   ├── mqtt/
│   │   ├── deployment.yaml                      # Mosquitto broker + ConfigMap
│   │   └── service.yaml                         # ClusterIP :1883
│   └── inference/
│       ├── Dockerfile                           # Python ONNX + MQTT + Prometheus
│       ├── inference.py                         # Single process: MQTT → ONNX → metrics
│       ├── deployment.yaml                      # Deployment + init container
│       ├── service.yaml                         # :9090 metrics
│       └── hpa.yaml                             # HPA 1–5 replicas, CPU 70%
│
└── cloud/
    ├── model-server/
    │   ├── Dockerfile                           # Flask HTTP server
    │   ├── server.py                            # /model, /version, /health
    │   └── deployment.yaml                      # Deployment + Service
    ├── model-sync/
    │   └── cronjob.yaml                         # CronJob + RBAC
    └── monitoring/
        ├── install.sh                           # Helm install Prometheus + Grafana
        ├── prometheus-values.yaml               # Pod annotation scrape config
        └── grafana-dashboard.json               # Geomap + timeseries + stats
```

---

## 7. Resource budget

### Edge node (Raspberry Pi — 2 GB RAM, 4 vCPU)

| Pod | CPU request | CPU limit | Mem request | Mem limit |
|-----|-------------|-----------|-------------|-----------|
| MQTT Broker | 50m | 200m | 64 Mi | 128 Mi |
| Inference App | 250m | 1000m | 256 Mi | 512 Mi |
| **Tổng** | **300m** | **1200m** | **320 Mi** | **640 Mi** |

### Device node

| Pod | CPU limit | Mem limit |
|-----|-----------|-----------|
| Frame Extractor | 500m | 512 Mi |

Với edge node 2 GB RAM: chạy được 1 MQTT + 2 inference replica thoải mái.

---

## 8. Quyết định thiết kế

| Quyết định | Lý do |
|-----------|-------|
| **3 tầng tách biệt** (devices / edge / cloud) | Phản ánh đúng physical topology. Mỗi tầng có trách nhiệm riêng, dễ scale độc lập. |
| **MQTT trên edge** (không phải cloud) | Giảm latency giữa broker và inference. Frame không cần đi qua cloud. |
| **Inference app tích hợp ONNX + MQTT + Prometheus** | Một container duy nhất, đơn giản. Không cần sidecar hay inter-process communication. `prometheus_client` xuất metrics trực tiếp. |
| **Python + onnxruntime** thay vì C++ | Đủ nhanh cho inference EfficientNet-Lite0 (~10–50ms). Tích hợp MQTT và Prometheus dễ hơn nhiều so với C++. |
| **MQTT pub/sub** | Decoupling devices ↔ inference. Buffering khi inference restart. Fan-out tự nhiên khi HPA scale. |
| **Init container** tải model | Pod luôn có model trước khi start. Không cần persistent volume. |
| **CronJob** sync model | Đơn giản, không cần webhook/operator. 5 phút delay chấp nhận được. |
| **Pod annotation** cho Prometheus | Không cần ServiceMonitor CRD. Tương thích Prometheus Helm chart mặc định. |
| **Grafana Geomap** | Dùng label `lat`, `lon` trên metric. Không cần GeoJSON hay database riêng. |
