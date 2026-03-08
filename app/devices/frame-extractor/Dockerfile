# ── Stage 1: Build ────────────────────────────────────────────────────
FROM alpine:3.19 AS builder

# Install build dependencies
RUN apk add --no-cache \
    build-base cmake \
    opencv-dev mosquitto-dev nlohmann-json curl-dev

# Build C++ Extractor
WORKDIR /build
COPY CMakeLists.txt extractor.cpp ./
RUN mkdir out && cd out \
    && cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/app .. \
    && make -j$(nproc) \
    && make install \
    && strip /app/bin/fire_frame_extractor

# ── Stage 2: Runtime (tiny) ──────────────────────────────────────────
FROM alpine:3.19

# Alpine's opencv package is highly optimized and strips out 
# huge GUI/X11/Audio bloat compared to Debian's libopencv
RUN apk add --no-cache \
    opencv \
    mosquitto-libs \
    curl

COPY --from=builder /app/bin/fire_frame_extractor /usr/local/bin/

ENV MQTT_HOST="mqtt-broker.fire-detection.svc"
ENV MQTT_PORT="1883"
ENV SOURCES_JSON="/config/sources.json"
ENV VIDEO_DIR="/videos"

ENTRYPOINT ["fire_frame_extractor"]
