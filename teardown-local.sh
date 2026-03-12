#!/bin/bash
# Teardown entire Edge Fire Detection stack from local Rancher Desktop cluster

echo "⚠️  Deleting Edge Fire Detection Stack..."

echo "----------------------------------------"
echo "☁️  Removing Cloud Monitoring Stack..."
echo "----------------------------------------"
kubectl delete -f app/cloud-monitoring/prometheus.yaml --ignore-not-found
kubectl delete -f app/cloud-monitoring/alertmanager.yaml --ignore-not-found
kubectl delete -f app/cloud-monitoring/grafana.yaml --ignore-not-found

echo "----------------------------------------"
echo "📹 Removing Edge Node Stack..."
echo "----------------------------------------"
kubectl delete -f app/edge/node/mqtt/ --ignore-not-found
kubectl delete -f app/edge/node/exporter/ --ignore-not-found
kubectl delete -f app/edge/node/inference/ --ignore-not-found
kubectl delete -f app/edge/node/frame-extractor/ --ignore-not-found

echo "----------------------------------------"
echo "🗑️ Teardown completed!"
kubectl get pods -A
