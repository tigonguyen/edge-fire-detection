#!/bin/bash
# Deploy distributed Edge Fire Detection stack
set -e

echo "🔥 Deploying Distributed Edge Fire Detection Stack..."

echo "----------------------------------------"
echo "☁️  Deploying Cloud Monitoring Stack (Master/AMD64)..."
echo "----------------------------------------"
kubectl apply -f app-distributed/cloud-monitoring/prometheus.yaml
kubectl apply -f app-distributed/cloud-monitoring/alertmanager.yaml
kubectl apply -f app-distributed/cloud-monitoring/grafana-datasource-cm.yaml
kubectl apply -f app-distributed/cloud-monitoring/grafana-dashboards-config-cm.yaml
kubectl apply -f app-distributed/cloud-monitoring/grafana-dashboard-json-cm.yaml
kubectl apply -f app-distributed/cloud-monitoring/grafana.yaml

echo "----------------------------------------"
echo "📹 Deploying Edge Node Stack (Worker/ARM64)..."
echo "----------------------------------------"
kubectl apply -f app-distributed/edge/node/mqtt/
kubectl apply -f app-distributed/edge/node/exporter/
kubectl apply -f app-distributed/edge/node/inference/
kubectl apply -f app-distributed/edge/node/frame-extractor/

echo "----------------------------------------"
echo "✅ Deployment requested!"
echo "Check pod distribution across nodes with:"
echo "kubectl get pods -o wide"
