# Triển khai k3s — Hướng dẫn nhanh

> Thiết kế chi tiết kiến trúc 3 tầng, luồng dữ liệu, và giải thích từng thành phần: xem [DESIGN.md](../DESIGN.md)

## Yêu cầu

- k3s cluster: cloud (master) + edge node(s) + device node(s)
- Helm 3 (cho Prometheus + Grafana)
- Docker (build image)

## 1. Cài k3s cluster

```bash
# Cloud master
bash deploy/k3s/install-master.sh

# Edge node
bash deploy/k3s/join-edge.sh <MASTER_IP> <TOKEN>
# Sau đó label: kubectl label node <edge> node-role=edge

# Device node
bash deploy/k3s/join-edge.sh <MASTER_IP> <TOKEN>
# Sau đó label: kubectl label node <device> node-role=device
```

## 2. Build Docker images

```bash
# Devices: frame extractor
docker build -t fire-frame-extractor deploy/devices/frame-extractor/

# Edge: inference (Python ONNX + MQTT + Prometheus)
docker build -t fire-inference deploy/edge/inference/

# Cloud: model server
docker build -t fire-model-server deploy/cloud/model-server/
```

## 3. Chuẩn bị dữ liệu

```bash
# Cloud node: copy ONNX model
sudo mkdir -p /opt/fire-detection/models
sudo cp fire_detection.onnx /opt/fire-detection/models/

# Device node: copy video files
sudo mkdir -p /opt/fire-detection/videos
sudo cp *.mp4 /opt/fire-detection/videos/
```

## 4. Triển khai

```bash
kubectl apply -f deploy/namespace.yaml

# Cloud
kubectl apply -f deploy/cloud/model-server/
kubectl apply -f deploy/cloud/model-sync/

# Edge
kubectl apply -f deploy/edge/mqtt/
kubectl apply -f deploy/edge/inference/

# Devices
kubectl apply -f deploy/devices/frame-extractor/

# Monitoring
bash deploy/cloud/monitoring/install.sh
```

Grafana: `http://<MASTER_IP>:30300` (admin / fire-admin)
Import dashboard từ `deploy/cloud/monitoring/grafana-dashboard.json`.

## 5. Kiểm tra

```bash
kubectl get pods -n fire-detection -o wide
kubectl logs -n fire-detection deployment/inference
kubectl get hpa -n fire-detection
```
