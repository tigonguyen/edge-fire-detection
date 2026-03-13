#!/bin/bash
# Teardown distributed Edge Fire Detection stack

echo "🚦 Tearing down Distributed Edge Fire Detection Stack..."

echo "----------------------------------------"
echo "☁️  Removing Cloud Monitoring Stack (Master/AMD64)..."
echo "----------------------------------------"
kubectl delete -f app-distributed/cloud-monitoring/prometheus.yaml --ignore-not-found
kubectl delete -f app-distributed/cloud-monitoring/alertmanager.yaml --ignore-not-found
kubectl delete -f app-distributed/cloud-monitoring/grafana.yaml --ignore-not-found

echo "----------------------------------------"
echo "📹 Removing Edge Node Stack (Worker/ARM64)..."
echo "----------------------------------------"
kubectl delete -f app-distributed/edge/node/mqtt/ --ignore-not-found
kubectl delete -f app-distributed/edge/node/exporter/ --ignore-not-found
kubectl delete -f app-distributed/edge/node/inference/ --ignore-not-found
kubectl delete -f app-distributed/edge/node/frame-extractor/ --ignore-not-found

echo "----------------------------------------"
echo "✅ Teardown complete!"
