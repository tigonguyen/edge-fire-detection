FROM python:3.9-slim
WORKDIR /app

RUN pip install --no-cache-dir opencv-python-headless paho-mqtt

COPY extractor.py /app/

CMD ["python", "extractor.py"]
