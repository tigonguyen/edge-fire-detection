# ── Stage 1: Build ────────────────────────────────────────────────────
FROM debian:bookworm-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake wget ca-certificates libmosquitto-dev \
    && rm -rf /var/lib/apt/lists/*

# Download ONNX Runtime (auto-detect arch)
ARG ONNX_VERSION=1.16.3
ARG TARGETPLATFORM
RUN set -e; \
    case "${TARGETPLATFORM}" in \
      linux/arm64) ORT_ARCH=aarch64 ;; \
      *)           ORT_ARCH=x64     ;; \
    esac; \
    wget -q "https://github.com/microsoft/onnxruntime/releases/download/v${ONNX_VERSION}/onnxruntime-linux-${ORT_ARCH}-${ONNX_VERSION}.tgz" \
    && tar xzf "onnxruntime-linux-${ORT_ARCH}-${ONNX_VERSION}.tgz" -C /opt \
    && rm "onnxruntime-linux-${ORT_ARCH}-${ONNX_VERSION}.tgz" \
    && ln -s "/opt/onnxruntime-linux-${ORT_ARCH}-${ONNX_VERSION}" /opt/onnxruntime
ENV ONNXRUNTIME_ROOT=/opt/onnxruntime

# Build
WORKDIR /build
COPY CMakeLists.txt inference.cpp ./
RUN mkdir out && cd out \
    && cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/app .. \
    && make -j$(nproc) \
    && make install \
    && strip /app/bin/fire_inference

# Collect only the mosquitto runtime .so (+ its cjson dep) into /staging
RUN mkdir /staging && \
    cp /usr/lib/*/libmosquitto.so* /staging/ && \
    cp /usr/lib/*/libcjson.so* /staging/ 2>/dev/null || true

# ── Stage 2: Distroless runtime (glibc + libstdc++ + libgomp + libssl) ─
FROM gcr.io/distroless/cc-debian12

COPY --from=builder /app/bin/fire_inference /usr/local/bin/fire_inference
COPY --from=builder /opt/onnxruntime/lib/ /opt/onnxruntime/lib/
COPY --from=builder /staging/ /usr/lib/

ENV LD_LIBRARY_PATH=/opt/onnxruntime/lib
EXPOSE 9090
ENTRYPOINT ["/usr/local/bin/fire_inference"]
