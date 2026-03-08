# prometheus/Dockerfile
# Prometheus Server with pre-configured rules
#
# Build:
#   docker build -t fire-prometheus .
#
# Run standalone:
#   docker run -d --name prometheus \
#     -p 9090:9090 \
#     -v $(pwd)/data:/prometheus \
#     fire-prometheus
#
# Run với custom exporter target:
#   docker run -d --name prometheus \
#     -p 9090:9090 \
#     -e EXPORTER_TARGET=host.docker.internal:8000 \
#     fire-prometheus

FROM prom/prometheus:v2.48.0

# Copy configuration files
COPY prometheus.yml /etc/prometheus/prometheus.yml
COPY alerts.yml /etc/prometheus/alerts.yml

# Create entrypoint script to support dynamic configuration
USER root
RUN mkdir -p /etc/prometheus/dynamic && \
    mkdir -p /prometheus && \
    chown -R nobody:nobody /etc/prometheus /prometheus

# Copy custom entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER nobody

# Expose port
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:9090/-/healthy || exit 1

ENTRYPOINT ["/entrypoint.sh"]
