#!/usr/bin/env bash
set -euo pipefail

# Install Prometheus + Grafana on k3s via Helm.
# Requires: helm (https://helm.sh/docs/intro/install/)

echo "Adding Helm repos..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

echo "Installing Prometheus..."
helm upgrade --install prometheus prometheus-community/prometheus \
  --namespace fire-detection \
  --set server.nodeSelector."node-role"=cloud \
  --set alertmanager.enabled=false \
  --set kube-state-metrics.enabled=false \
  --set prometheus-node-exporter.enabled=false \
  --set prometheus-pushgateway.enabled=false \
  --set server.persistentVolume.enabled=false \
  --set server.resources.limits.memory=512Mi \
  --set server.resources.limits.cpu=500m \
  -f "$(dirname "$0")/prometheus-values.yaml"

echo "Installing Grafana..."
helm upgrade --install grafana grafana/grafana \
  --namespace fire-detection \
  --set nodeSelector."node-role"=cloud \
  --set service.type=NodePort \
  --set service.nodePort=30300 \
  --set persistence.enabled=false \
  --set resources.limits.memory=256Mi \
  --set resources.limits.cpu=200m \
  --set adminPassword=fire-admin

echo ""
echo "Grafana: http://<MASTER_IP>:30300  (admin / fire-admin)"
echo "Import dashboard from deploy/monitoring/grafana-dashboard.json"
