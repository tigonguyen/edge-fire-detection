#!/bin/bash
# Rebuild all Edge Fire Detection Docker Images with unified naming convention

set -e

echo "----------------------------------------"
echo "📦 Building 'edge-fire-exporter'..."
echo "----------------------------------------"
cd app/edge/node/exporter/src
docker build -t edge-fire-exporter:latest .
cd ../../../../..

echo "----------------------------------------"
echo "📦 Building 'edge-fire-inference'..."
echo "----------------------------------------"
docker build -t edge-fire-inference:latest -f app/edge/node/inference/Dockerfile .

echo "----------------------------------------"
echo "📦 Building 'edge-fire-extractor'..."
echo "----------------------------------------"
docker build -t edge-fire-extractor:latest -f app/edge/node/frame-extractor/Dockerfile .

echo "----------------------------------------"
echo "📦 Tagging NGINX Alpine as 'edge-fire-nginx'..."
echo "----------------------------------------"
docker pull nginx:alpine
docker tag nginx:alpine edge-fire-nginx:latest

echo "----------------------------------------"
echo "📦 Building 'edge-fire-prometheus'..."
echo "----------------------------------------"
cd app/cloud-monitoring/prometheus
docker build -t edge-fire-prometheus:latest .
cd ../../..

echo "----------------------------------------"
echo "📦 Building 'edge-fire-alertmanager'..."
echo "----------------------------------------"
cd app/cloud-monitoring/alertmanager
docker build -t edge-fire-alertmanager:latest .
cd ../../..

echo "----------------------------------------"
echo "📦 Building 'edge-fire-grafana'..."
echo "----------------------------------------"
cd app/cloud-monitoring/grafana
docker build -t edge-fire-grafana:latest .
cd ../../..

echo "----------------------------------------"
echo "✅ All local images successfully rebuilt!"
echo "Run 'bash deploy-local.sh' to re-deploy your cluster."
docker images | grep edge-fire
