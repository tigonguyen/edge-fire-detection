FROM python:3.11-slim

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir paho-mqtt==2.1.0 opencv-python-headless

# Copy application code
COPY app/edge/node/frame-extractor/extractor.py .

# Copy video files directly into the image
RUN mkdir -p /videos
COPY videos/*.mp4 /videos/

# Configure environment variables
ENV PYTHONUNBUFFERED=1
ENV MQTT_BROKER="mqtt-broker-node.default.svc"
ENV MQTT_PORT="1883"
ENV VIDEO_DIR="/videos"
ENV FPS="2"

# Run the extractor
CMD ["python", "extractor.py"]
