FROM python:3.11-slim

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install explicit torch stack constraints + opencv & mqtt
RUN pip install --no-cache-dir \
    "torch<2.4.0" \
    "torchvision<0.19.0" \
    "timm" \
    "paho-mqtt==2.1.0" \
    "opencv-python-headless" \
    "numpy" \
    "Pillow"

# Copy application code
COPY app/edge/binhphuoc/inference/inference.py .

# Mount the static PyTorch model
RUN mkdir -p /model
COPY fire_detection_best.pth /model/

# Configure
ENV PYTHONUNBUFFERED=1
ENV MQTT_BROKER="mqtt-broker-binhphuoc.default.svc"
ENV MQTT_PORT="1883"
ENV MODEL_PATH="/model/fire_detection_best.pth"

CMD ["python", "inference.py"]
