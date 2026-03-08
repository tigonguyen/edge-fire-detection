FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir opencv-python-headless paho-mqtt
WORKDIR /app
COPY extractor.py .
CMD ["python", "extractor.py"]
