# mosquitto/Dockerfile
# MQTT Broker - Eclipse Mosquitto
#
# Build:
#   docker build -t fire-mosquitto .
#
# Run standalone:
#   docker run -d --name mosquitto \
#     -p 1883:1883 \
#     -p 9001:9001 \
#     -v $(pwd)/data:/mosquitto/data \
#     -v $(pwd)/log:/mosquitto/log \
#     fire-mosquitto
#
# Test:
#   mosquitto_pub -h localhost -t test -m "hello"
#   mosquitto_sub -h localhost -t test

FROM eclipse-mosquitto:2

# Copy config
COPY mosquitto.conf /mosquitto/config/mosquitto.conf

# Create directories
RUN mkdir -p /mosquitto/data /mosquitto/log && \
    chown -R mosquitto:mosquitto /mosquitto

# Expose ports
# 1883: MQTT
# 9001: WebSocket
EXPOSE 1883 9001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD mosquitto_sub -h localhost -t '$SYS/broker/uptime' -C 1 -W 5 || exit 1

CMD ["mosquitto", "-c", "/mosquitto/config/mosquitto.conf"]
