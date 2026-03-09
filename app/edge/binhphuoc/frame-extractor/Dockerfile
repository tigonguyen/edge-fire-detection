# ── Stage 1: Build ────────────────────────────────────────────────────
FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake wget ca-certificates \
    libopencv-dev libmosquitto-dev nlohmann-json3-dev libcurl4-openssl-dev

WORKDIR /build
COPY CMakeLists.txt extractor.cpp ./
# Build C++ Extractor
RUN mkdir out && cd out \
    && cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/app .. \
    && make -j$(nproc) \
    && make install \
    && strip /app/bin/fire_frame_extractor

# ── Stage 2: Runtime ──────────────────────────────────────────────────
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libopencv-core406t64 libopencv-imgproc406t64 libopencv-videoio406t64 \
    libmosquitto1 libcurl4 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/bin/fire_frame_extractor /usr/local/bin/

ENV MQTT_HOST="mqtt-broker.default.svc"
ENV MQTT_PORT="1883"
ENV SOURCES_JSON="/config/sources.json"
ENV VIDEO_DIR="/videos"
RUN mkdir -p /videos

ENTRYPOINT ["fire_frame_extractor"]
