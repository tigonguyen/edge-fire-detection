# grafana/Dockerfile
# Grafana Dashboard with pre-configured datasources
#
# Build:
#   docker build -t edge-fire-grafana .
#
# Run standalone:
#   docker run -d --name grafana \
#     -p 3000:3000 \
#     -e PROMETHEUS_URL=http://host.docker.internal:9090 \
#     edge-fire-grafana
#
# Default login: admin / admin123

FROM grafana/grafana:10.2.2

# Install plugins
ENV GF_INSTALL_PLUGINS=grafana-worldmap-panel

# Copy configuration
COPY grafana.ini /etc/grafana/grafana.ini
COPY provisioning /etc/grafana/provisioning

# Copy custom entrypoint
USER root
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create directories
RUN mkdir -p /var/lib/grafana/images && \
    chown -R grafana:root /var/lib/grafana

USER grafana

# Environment variables
ENV GF_SECURITY_ADMIN_USER=admin \
    GF_SECURITY_ADMIN_PASSWORD=admin123 \
    PROMETHEUS_URL=http://prometheus:9090 \
    ALERTMANAGER_URL=http://alertmanager:9093

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -q --spider http://localhost:3000/api/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
