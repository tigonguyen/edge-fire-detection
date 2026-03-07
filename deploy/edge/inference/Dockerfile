# ── Stage 1: Build ────────────────────────────────────────────────────
FROM debian:bookworm-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake wget ca-certificates libmosquitto-dev \
    && rm -rf /var/lib/apt/lists/*

# Download ONNX Runtime
ARG ONNX_VERSION=1.16.3
ARG TARGETARCH=x64
RUN wget -q https://github.com/microsoft/onnxruntime/releases/download/v${ONNX_VERSION}/onnxruntime-linux-${TARGETARCH}-${ONNX_VERSION}.tgz \
    && tar xzf onnxruntime-linux-${TARGETARCH}-${ONNX_VERSION}.tgz -C /opt \
    && rm onnxruntime-linux-${TARGETARCH}-${ONNX_VERSION}.tgz
ENV ONNXRUNTIME_ROOT=/opt/onnxruntime-linux-${TARGETARCH}-${ONNX_VERSION}

# Build
WORKDIR /build
COPY CMakeLists.txt inference.cpp ./
RUN mkdir out && cd out \
    && cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/app .. \
    && make -j$(nproc) \
    && make install \
    && strip /app/bin/fire_inference

# ── Stage 2: Runtime (tiny) ──────────────────────────────────────────
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmosquitto1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/bin/fire_inference /usr/local/bin/

ARG ONNX_VERSION=1.16.3
ARG TARGETARCH=x64
COPY --from=builder /opt/onnxruntime-linux-${TARGETARCH}-${ONNX_VERSION}/lib /opt/onnxruntime/lib
ENV LD_LIBRARY_PATH=/opt/onnxruntime/lib

EXPOSE 9090
ENTRYPOINT ["fire_inference"]
