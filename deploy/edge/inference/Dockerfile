FROM python:3.11-slim
RUN pip install --no-cache-dir onnxruntime paho-mqtt prometheus_client numpy
WORKDIR /app
COPY inference.py .
EXPOSE 9090
CMD ["python", "inference.py"]
