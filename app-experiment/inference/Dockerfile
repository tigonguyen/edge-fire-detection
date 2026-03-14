FROM pytorch/pytorch:2.2.0-cuda11.8-cudnn8-runtime

WORKDIR /app

# Install standard dependencies
RUN apt-get update && apt-get install -y libglib2.0-0 libsm6 libxext6 libxrender-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir opencv-python-headless paho-mqtt timm pillow numpy torchvision

COPY inference.py /app/

CMD ["python", "inference.py"]
