#!/bin/sh
# grafana/entrypoint.sh
# Custom entrypoint để hỗ trợ dynamic datasource configuration

set -e

DATASOURCE_FILE="/etc/grafana/provisioning/datasources/prometheus.yml"

# Update Prometheus URL in datasource
if [ -n "$PROMETHEUS_URL" ]; then
    echo "Configuring Prometheus datasource: $PROMETHEUS_URL"
    sed -i "s|http://prometheus:9090|${PROMETHEUS_URL}|g" $DATASOURCE_FILE 2>/dev/null || true
fi

if [ -n "$ALERTMANAGER_URL" ]; then
    echo "Configuring Alertmanager datasource: $ALERTMANAGER_URL"
    sed -i "s|http://alertmanager:9093|${ALERTMANAGER_URL}|g" $DATASOURCE_FILE 2>/dev/null || true
fi

# Start Grafana
exec /run.sh "$@"
