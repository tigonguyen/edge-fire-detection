# Multi-stage build for minimal image size
FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ONNX Runtime
ARG ONNX_VERSION=1.16.3
RUN wget -q https://github.com/microsoft/onnxruntime/releases/download/v${ONNX_VERSION}/onnxruntime-linux-x64-${ONNX_VERSION}.tgz \
    && tar xzf onnxruntime-linux-x64-${ONNX_VERSION}.tgz -C /opt \
    && rm onnxruntime-linux-x64-${ONNX_VERSION}.tgz
ENV ONNXRUNTIME_ROOT=/opt/onnxruntime-linux-x64-${ONNX_VERSION}

WORKDIR /build
COPY CMakeLists.txt include/ src/ ./
RUN mkdir build && cd build \
    && cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/app .. \
    && make -j$(nproc) && make install

# Runtime stage: tiny image
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/bin/fire_backend /usr/local/bin/
ARG ONNX_VERSION=1.16.3
COPY --from=builder /opt/onnxruntime-linux-x64-${ONNX_VERSION} /opt/onnxruntime/
ENV LD_LIBRARY_PATH=/opt/onnxruntime/lib
WORKDIR /app
# Default: expect model at /app/model/fire_detection.onnx
ENV MODEL_PATH=/app/model/fire_detection.onnx
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/fire_backend"]
CMD ["/app/model/fire_detection.onnx"]
