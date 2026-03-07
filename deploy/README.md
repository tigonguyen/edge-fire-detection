# Triển khai k3s — Hướng dẫn nhanh

> Thiết kế chi tiết kiến trúc, luồng dữ liệu, và giải thích từng thành phần: xem [DESIGN.md](../DESIGN.md)

## Yêu cầu

- k3s (master node: cloud, edge node: Raspberry Pi hoặc tương đương)
- Helm 3 (cho Prometheus + Grafana)
- Docker (build image)

## 1. Cài k3s cluster

```bash
# Master (cloud)
bash deploy/k3s/install-master.sh

# Edge node — cần MASTER_IP và TOKEN từ output master
bash deploy/k3s/join-edge.sh <MASTER_IP> <TOKEN>
```

## 2. Build Docker images

```bash
# Model server
docker build -t fire-model-server deploy/model-server/

# Frame extractor
docker build -t fire-frame-extractor deploy/frame-extractor/

# MQTT bridge
docker build -t fire-mqtt-bridge -f deploy/inference/Dockerfile.bridge deploy/inference/

# C++ backend (dùng Dockerfile từ app/)
docker build -t fire-backend app/
```

## 3. Chuẩn bị dữ liệu trên node

```bash
# Cloud node: copy ONNX model
sudo mkdir -p /opt/fire-detection/models
sudo cp fire_detection.onnx /opt/fire-detection/models/

# Edge node: copy video files
sudo mkdir -p /opt/fire-detection/videos
sudo cp *.mp4 /opt/fire-detection/videos/
```

## 4. Triển khai workload

```bash
kubectl apply -f deploy/namespace.yaml
kubectl apply -f deploy/mqtt/
kubectl apply -f deploy/model-server/
kubectl apply -f deploy/frame-extractor/
kubectl apply -f deploy/inference/
kubectl apply -f deploy/model-sync/
```

## 5. Cài monitoring

```bash
bash deploy/monitoring/install.sh
```

Grafana: `http://<MASTER_IP>:30300` (admin / fire-admin)

Import dashboard từ `deploy/monitoring/grafana-dashboard.json`.

## Kiểm tra

```bash
kubectl get pods -n fire-detection
kubectl logs -n fire-detection deployment/inference -c mqtt-bridge
kubectl get hpa -n fire-detection
```
