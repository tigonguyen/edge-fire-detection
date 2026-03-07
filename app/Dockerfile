FROM ubuntu:22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake wget ca-certificates && rm -rf /var/lib/apt/lists/*

ARG ONNX_VERSION=1.16.3
RUN wget -q https://github.com/microsoft/onnxruntime/releases/download/v${ONNX_VERSION}/onnxruntime-linux-x64-${ONNX_VERSION}.tgz \
    && tar xzf onnxruntime-linux-x64-${ONNX_VERSION}.tgz -C /opt \
    && rm onnxruntime-linux-x64-${ONNX_VERSION}.tgz
ENV ONNXRUNTIME_ROOT=/opt/onnxruntime-linux-x64-${ONNX_VERSION}

WORKDIR /build
COPY CMakeLists.txt ./
COPY include/ include/
COPY src/ src/
RUN mkdir out && cd out \
    && cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/app .. \
    && make -j$(nproc) && make install

FROM ubuntu:22.04
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/bin/fire_backend /usr/local/bin/
ARG ONNX_VERSION=1.16.3
COPY --from=builder /opt/onnxruntime-linux-x64-${ONNX_VERSION}/lib /opt/onnxruntime/lib
ENV LD_LIBRARY_PATH=/opt/onnxruntime/lib
ENTRYPOINT ["fire_backend"]
