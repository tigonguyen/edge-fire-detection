#!/bin/bash
# Deploy entire Edge Fire Detection stack to local Rancher Desktop cluster

set -e

echo "🔥 Deploying Edge Fire Detection Stack..."

echo "----------------------------------------"
echo "☁️  Deploying Cloud Monitoring Stack..."
echo "----------------------------------------"
kubectl apply -f app/cloud-monitoring/prometheus.yaml
kubectl apply -f app/cloud-monitoring/alertmanager.yaml
kubectl apply -f app/cloud-monitoring/grafana.yaml

echo "----------------------------------------"
echo "📹 Deploying Edge Node Stack..."
echo "----------------------------------------"
kubectl apply -f app/edge/node/mqtt/
kubectl apply -f app/edge/node/exporter/
kubectl apply -f app/edge/node/inference/
kubectl apply -f app/edge/node/frame-extractor/

echo "----------------------------------------"
echo "✅ Deployment completed!"
echo "- Prometheus: http://localhost:9090"
echo "- Alertmanager: http://localhost:9093"
echo "- Grafana: http://localhost:3000 (admin/admin)"
echo "- Exporter Metrics: http://localhost:8080/metrics"

kubectl get pods -A
