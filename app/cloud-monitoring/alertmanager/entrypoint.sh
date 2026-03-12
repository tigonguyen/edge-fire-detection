#!/bin/sh
# alertmanager/entrypoint.sh
# Custom entrypoint để hỗ trợ environment variables trong config

set -e

CONFIG_FILE="/etc/alertmanager/alertmanager.yml"
CONFIG_RUNTIME="/tmp/alertmanager.yml"

# Copy config and substitute environment variables
cp "$CONFIG_FILE" "$CONFIG_RUNTIME"

# Replace environment variables in config
# Use defaults if not set to prevent YAML parsing errors
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-placeholder_token}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-0}"

if [ "$TELEGRAM_BOT_TOKEN" = "placeholder_token" ]; then
    echo "Warning: TELEGRAM_BOT_TOKEN not set - Telegram notifications disabled"
else
    echo "Telegram Bot Token configured"
fi

if [ "$TELEGRAM_CHAT_ID" = "0" ]; then
    echo "Warning: TELEGRAM_CHAT_ID not set - Telegram notifications disabled"
else
    echo "Telegram Chat ID configured: $TELEGRAM_CHAT_ID"
fi

# Always substitute the variables (with defaults if not set)
sed -i "s|\${TELEGRAM_BOT_TOKEN}|$TELEGRAM_BOT_TOKEN|g" "$CONFIG_RUNTIME"
sed -i "s|\${TELEGRAM_CHAT_ID}|$TELEGRAM_CHAT_ID|g" "$CONFIG_RUNTIME"

# Start Alertmanager with runtime config
exec /bin/alertmanager \
    --config.file="$CONFIG_RUNTIME" \
    --storage.path=/alertmanager \
    "$@"
