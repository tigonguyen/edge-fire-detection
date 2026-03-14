FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir opencv-python-headless paho-mqtt timm pillow numpy

COPY inference.py /app/

CMD ["python", "inference.py"]
