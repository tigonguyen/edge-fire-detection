#!/bin/sh
# prometheus/entrypoint.sh
# Custom entrypoint để hỗ trợ dynamic configuration

set -e

# Default values - use container names in fire-detection-network
EXPORTER_TARGET=${EXPORTER_TARGET:-"fire-exporter:8000"}
ALERTMANAGER_TARGET=${ALERTMANAGER_TARGET:-"fire-alertmanager:9093"}

# Generate dynamic config if needed
CONFIG_FILE="/etc/prometheus/prometheus.yml"
CONFIG_RUNTIME="/tmp/prometheus.yml"

# Copy config to runtime location
cp "$CONFIG_FILE" "$CONFIG_RUNTIME"

# Replace targets in runtime config
echo "Using exporter target: $EXPORTER_TARGET"
sed -i "s|fire-exporter:8000|${EXPORTER_TARGET}|g" "$CONFIG_RUNTIME"

echo "Using alertmanager target: $ALERTMANAGER_TARGET"
sed -i "s|fire-alertmanager:9093|${ALERTMANAGER_TARGET}|g" "$CONFIG_RUNTIME"

# Start Prometheus with runtime config
exec /bin/prometheus \
    --config.file="$CONFIG_RUNTIME" \
    --storage.tsdb.path=/prometheus \
    --web.enable-lifecycle \
    --storage.tsdb.retention.time=30d \
    --web.console.libraries=/usr/share/prometheus/console_libraries \
    --web.console.templates=/usr/share/prometheus/consoles \
    "$@"
