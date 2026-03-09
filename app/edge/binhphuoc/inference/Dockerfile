# inference/Dockerfile
# Simple Python Mock Inference Engine
#
# Build:
#   docker build -t fire-inference-python .

FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies (paho-mqtt for connection, opencv/numpy for mock image array)
RUN pip install --no-cache-dir paho-mqtt==2.1.0 opencv-python-headless numpy

# Copy application code
COPY inference.py .

# Environment variables (defaults)
ENV MQTT_BROKER=localhost \
    MQTT_PORT=1883 \
    INTERVAL_SECONDS=300 \
    PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ps aux | grep "[p]ython inference.py" || exit 1

# Run application
CMD ["python", "inference.py"]
