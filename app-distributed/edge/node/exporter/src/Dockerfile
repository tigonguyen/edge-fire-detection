# exporter/Dockerfile
# Fire Detection Prometheus Exporter
#
# Build:
#   docker build -t edge-fire-exporter .
#
# Run standalone:
#   docker run -d --name exporter \
#     -p 8000:8000 \
#     -e MQTT_BROKER=host.docker.internal \
#     -e MQTT_PORT=1883 \
#     -e TELEGRAM_BOT_TOKEN=your_token \
#     -e TELEGRAM_CHAT_ID=your_chat_id \
#     -v $(pwd)/../images:/app/images \
#     edge-fire-exporter
#
# Debug mode (with shell):
#   docker run -it --rm \
#     -p 8000:8000 \
#     -e MQTT_BROKER=host.docker.internal \
#     -v $(pwd)/../images:/app/images \
#     edge-fire-exporter /bin/bash

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./

# Create directories
RUN mkdir -p /app/images

# Environment variables (defaults)
ENV MQTT_BROKER=localhost \
    MQTT_PORT=1883 \
    IMAGES_DIR=/app/images \
    IMAGE_BASE_URL=http://localhost:8080/images \
    TELEGRAM_BOT_TOKEN="" \
    TELEGRAM_CHAT_ID=""

# Expose metrics port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "main.py"]
