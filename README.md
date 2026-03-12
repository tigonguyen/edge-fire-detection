# Distributed Multi-Region Edge Wildfire Detection

This project simulates a highly distributed, **edge-native wildfire detection pipeline** orchestrated on Kubernetes. It was engineered to process massive multi-region video feeds directly at the edge, utilizing deep learning to identify wildfires in real-time, and routing lightweight, geo-tagged telemetry to a centralized Cloud environment. 

This decentralized approach prevents cloud bandwidth saturation and ensures rapid, localized response capabilities without sacrificing centralized visibility.

---

## 🏗 System Architecture

The ecosystem strictly adheres to an Edge-to-Cloud topology, physically mimicking a real-world deployment across vast Vietnamese forests (Đà Lạt, Bạch Mã, Hoàng Liên Sơn).

```mermaid
flowchart TD
    subgraph "🌲 Edge Kubernetes Sites (Cameras & Compute)"
        A(["Drone / Static Camera MP4 Feeds"])
        B["Edge Frame Extractor (Python/OpenCV)"]
        C(("Edge MQTT Broker"))
        D["Edge AI Inference Engine (PyTorch)"]
        
        A -->|Reads mp4s| B
        B -->|Publishes 2FPS Resized Frames| C
        C -->|Subscribes to raw frames| D
    end
    
    subgraph "☁️ Central Cloud Infrastructure (Aggregator & Alerting)"
        E["Cloud Exporter Daemon"]
        F[("Cloud Prometheus TSDB")]
        G["Prometheus AlertManager"]
        H["Grafana Dashboard & GeoMap"]
        
        D -->|Publishes JSON Alert telemetry| E
        E -->|Translates to Prometheus /metrics| F
        F -->|Evaluates triggers| G
        F -->|Real-time Visualization| H
    end
    
    style A fill:#a8edea,stroke:#000,stroke-width:2px,color:#000
    style B fill:#fbc2eb,stroke:#000,stroke-width:2px,color:#000
    style C fill:#fdfbfb,stroke:#000,stroke-width:2px,color:#000
    style D fill:#f6d365,stroke:#000,stroke-width:2px,color:#000
    style E fill:#84fab0,stroke:#000,stroke-width:2px,color:#000
    style F fill:#cfd9df,stroke:#000,stroke-width:2px,color:#000
    style G fill:#ffecd2,stroke:#000,stroke-width:2px,color:#000
    style H fill:#a1c4fd,stroke:#000,stroke-width:2px,color:#000
```

### 1. Edge Components (`app/edge/`)
Each geographic quadrant deploys an autonomous Edge stack. This isolates processing logic close to the data source.

- **Frame Extractor (`extractor.py`)**: 
  - Simulates physical IoT cameras or drone patrols.
  - Dynamically mounts all `.mp4` video files representing regional feeds.
  - Leverages OpenCV (`cv2`) to extract raw video, rescale the buffers to `224x224` (optimal for our AI), and throttle the feed to exactly `2 Frames Per Second (FPS)`.
  - Publishes the byte-encoded image arrays to localized MQTT topics (e.g., `frames/bachma`).

- **MQTT Broker (`mosquitto`)**: 
  - The ultra-fast, lightweight intra-edge message bus. 
  - Required to orchestrate communication between the Extractor and Inference engines without an external network dependency. 

- **AI Inference Engine (`inference.py`)**: 
  - The brain of the operation. Embedded inside this container is our pre-trained PyTorch checkpoint (`fire_detection_best.pth`).
  - Utilizes `timm` (PyTorch Image Models) to instantly spin up the `EfficientNet-Lite` computer vision architecture.
  - Processes the RGB frames off the MQTT bus at sub-30ms latency.
  - **Geo-Tagging**: Dynamically maps the incoming camera stream (`bachma`, `dalat`, `hoanglienson`) to hardcoded real-world Latitude and Longitude GPS coordinates.
  - **Edge-Throttling**: If a fire is detected with `>70% Confidence`, it converts the frame to `Base64` and dispatches lightweight JSON telemetry over MQTT to the Cloud. However, it suppresses notifications to a maximum of **one alert per 10 seconds per camera** to prevent flood attacks.

### 2. Cloud Components (`app/cloud-monitoring/`)
The centralized environment is strictly responsible for telemetry aggregation, transformation, and high-level visualization.

- **Python Exporter (`exporter/`)**: 
  - Acts as the gateway between the Edge Sites and the Cloud databases.
  - Listens to the `wildfire/alerts` MQTT channels from *all* Edge nodes globally. 
  - Parses the inbound JSON and exposes them as native Prometheus `Gauge` endpoints. 
  - **Dynamic Cool-down Logic**: The Exporter enforces a strict `30-second cooldown block`. If an edge camera detects a continuous fire spanning minutes, instead of spamming Telegram/Prometheus with hundreds of Alerts, the Exporter absorbs the spam, emitting a single `fire_alert_info` metric containing the AI probability, while simultaneously ticking up a dedicated `fire_alert_frames_count` metric used to visually enlarge the blip on the map without firing text alerts.

- **Prometheus & AlertManager (`kube-prometheus-stack`)**: 
  - The industry-standard Kubernetes observability stack.
  - Continuously scrapes the `/metrics` endpoint on the Exporter pod.
  - Evaluates `alerts.yml` rules to trigger critical pagers.

- **Grafana Visualization (`dashboards/fire-detection.json`)**: 
  - Fully bespoke analytics UI.
  - Includes a real-time **Geomap Panel**, dynamically fed global coordinates from the Edge Inference payloads.
  - Maps `fire_alert_frames_count` directly to the `radius` of organic bubbles on the map. As a wildfire persists (count rises), the red circle representing the fire dynamically balloons in size on the Vietnamese map, drawing immediate geographical attention to worsening events.

---

## 🚀 Prerequisites

- An active local Kubernetes orchestrator (Rancher Desktop, Docker Desktop, or Minikube)
- Configured local storage provisioners
- `kubectl` 
- Local Docker Daemon 
- `Python 3.11+` (For standalone testing without containers - optional)

---

## ⚙️ Local Development Quick Start

The entire multi-region ecosystem can be instantly scaffolded onto your local machine for rapid prototyping using our automated configuration scripts.

### 1. Build the Decentralized Docker Images
The pipeline relies on heavily customized Python and Alpine configurations for its Edge and Cloud components. Running this script guarantees all 6 required images are unified under the `edge-fire-[component]` naming convention inside your local Docker daemon cache, bypassing the need for an external container registry.

```bash
# This cleans up stale images and builds Extractor, Inference, Mqtt, Exporter, Prometheus, AlertManager, and Grafana from source.
./build-local.sh
```

### 2. Deploy the End-to-End Cluster
We have abstracted away the complex dependency ordering of spinning up the Cloud aggregators before the Edge subscribers. A single shell script sequentially applies the entire directory tree (`app/cloud-monitoring/` & `app/edge/node/`).

```bash
./deploy-local.sh
```

### 3. Live Verification

Wait approximately 30-45 seconds for Kubernetes to provision all 7 independent services and for the Edge AI `EfficientNet` model to bootstrap into VRAM.

Once the `deploy-local.sh` completion message appears, inspect the Edge inference engine telemetry streaming in real-time off the internal MQTT bus using kubectl:

```bash
kubectl logs -l app=inference -f
```

*(Expected output showing parallel regional evaluation)*
> `[bachma] 🌲 NORMAL conf=0.983 (latency=26.9ms)`
> `[hoanglienson] 🔥 FIRE conf=0.995 (latency=28.3ms)`
> `  -> Dispatched ALERT alert_1773161512_273 payload to wildfire/alerts!`
> `[dalat] 🌲 NORMAL conf=0.953 (latency=17.0ms)`

#### Visualizing the Outbreak
With everything deployed locally, our predefined K8s `NodePort`/`ClusterIP` services automatically bind to localhost for instantaneous access.

- **Grafana Visualization**: `http://localhost:3000`
  - *Login credentials*: `admin` / `admin`
  - This natively provisions a real-time **Geomap Panel**, dynamically fed global coordinates from the Edge Inference payloads showing organic red bubbles expanding according to ongoing wildfire metrics.

- **Prometheus TSDB**: `http://localhost:9090`
- **Prometheus AlertManager**: `http://localhost:9093`
- **Exporter Raw Metrics**: `http://localhost:8080/metrics`

### 4. Teardown Sandbox
Instantly nuke the entire Kubernetes topology, stopping all node processing and releasing memory.

```bash
./teardown-local.sh
```
