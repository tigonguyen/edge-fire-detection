#!/bin/bash
# Multi-Architecture Build Script for Edge Fire Detection
set -e

ARCH=$(uname -m)

echo "========================================"
echo "🌍 Detected Architecture: $ARCH"
echo "========================================"

if [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "amd64" ]; then
    echo "☁️ Building Cloud Components for GCP Master (amd64)..."
    
    cd app-distributed/cloud-monitoring/prometheus
    docker build -t edge-fire-prometheus:latest .
    cd ../../..

    cd app-distributed/cloud-monitoring/alertmanager
    docker build -t edge-fire-alertmanager:latest .
    cd ../../..

    cd app-distributed/cloud-monitoring/grafana
    docker build -t edge-fire-grafana:latest .
    cd ../../..
    
    echo "✅ Cloud image build complete."

elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    echo "📹 Building Edge Components for M1 Worker (arm64)..."
    
    cd app-distributed/edge/node/exporter/src
    docker build -t edge-fire-exporter:latest .
    cd ../../../../..

    docker build -t edge-fire-inference:latest -f app-distributed/edge/node/inference/Dockerfile .
    docker build -t edge-fire-extractor:latest -f app-distributed/edge/node/frame-extractor/Dockerfile .
    
    docker pull nginx:alpine
    docker tag nginx:alpine edge-fire-nginx:latest
    
    echo "✅ Edge image build complete."
else
    echo "❌ Unknown architecture: $ARCH"
    exit 1
fi
