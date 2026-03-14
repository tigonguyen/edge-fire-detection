#!/bin/bash
echo "Building Experiment Images for Architecture: $(uname -m)"

echo "Building Extractor..."
docker build --network host -t experiment-extractor:latest ./app-experiment/extractor

echo "Building Inference..."
docker build --network host -t experiment-inference:latest ./app-experiment/inference

# Ensure k3s/containerd can see it if running locally on Mac
if command -v k3s >/dev/null 2>&1; then
    echo "Importing images to k3s containerd..."
    docker save experiment-extractor:latest | sudo k3s ctr images import -
    docker save experiment-inference:latest | sudo k3s ctr images import -
fi

echo "Done!"
