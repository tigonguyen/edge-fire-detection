# alertmanager/Dockerfile
# Prometheus Alertmanager with Telegram integration
#
# Build:
#   docker build -t fire-alertmanager .
#
# Run standalone:
#   docker run -d --name alertmanager \
#     -p 9093:9093 \
#     -e TELEGRAM_BOT_TOKEN=your_token \
#     -e TELEGRAM_CHAT_ID=your_chat_id \
#     fire-alertmanager

FROM prom/alertmanager:v0.26.0

# Copy configuration
COPY alertmanager.yml /etc/alertmanager/alertmanager.yml

# Copy custom entrypoint
USER root
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && \
    mkdir -p /alertmanager && \
    chown -R nobody:nobody /alertmanager
USER nobody

# Expose port
EXPOSE 9093

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:9093/-/healthy || exit 1

ENTRYPOINT ["/entrypoint.sh"]
