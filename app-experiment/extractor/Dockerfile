FROM python:3.9-slim
WORKDIR /app

RUN apt-get update && apt-get install -y libglib2.0-0 libsm6 libxext6 libxrender-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir opencv-python-headless paho-mqtt

COPY extractor.py /app/

CMD ["python", "extractor.py"]
