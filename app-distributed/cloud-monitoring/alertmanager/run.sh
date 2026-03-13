#!/bin/bash
# alertmanager/run.sh
# Script để chạy Alertmanager độc lập

set -e

CONTAINER_NAME="edge-fire-alertmanager"
IMAGE_NAME="edge-fire-alertmanager"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Shared Docker network
NETWORK_NAME=${NETWORK_NAME:-"fire-detection-network"}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Tạo network nếu chưa có
ensure_network() {
    if ! docker network inspect $NETWORK_NAME >/dev/null 2>&1; then
        echo -e "${YELLOW}Creating network: $NETWORK_NAME${NC}"
        docker network create $NETWORK_NAME
    fi
}

# Load .env if exists
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(cat "$PROJECT_DIR/.env" | grep -v '^#' | xargs)
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}      Alertmanager - Standalone         ${NC}"
echo -e "${GREEN}========================================${NC}"

# Parse arguments
ACTION=${1:-"start"}

# Environment variables
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-""}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID:-""}

case $ACTION in
    build)
        echo -e "${YELLOW}Building image...${NC}"
        docker build -t $IMAGE_NAME "$SCRIPT_DIR"
        echo -e "${GREEN}Build complete!${NC}"
        ;;

    start)
        # Stop if running
        docker stop $CONTAINER_NAME 2>/dev/null || true
        docker rm $CONTAINER_NAME 2>/dev/null || true

        # Ensure network exists
        ensure_network

        # Build if image doesn't exist
        if [[ "$(docker images -q $IMAGE_NAME 2>/dev/null)" == "" ]]; then
            echo -e "${YELLOW}Building image...${NC}"
            docker build -t $IMAGE_NAME "$SCRIPT_DIR"
        fi

        # Create data directory with proper permissions for nobody user
        mkdir -p "$SCRIPT_DIR/data"
        chmod 777 "$SCRIPT_DIR/data"

        echo -e "${YELLOW}Starting Alertmanager...${NC}"
        echo -e "${CYAN}Network: $NETWORK_NAME${NC}"

        if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
            echo -e "${CYAN}Telegram notifications enabled${NC}"
        else
            echo -e "${YELLOW}Warning: TELEGRAM_BOT_TOKEN not set${NC}"
        fi

        docker run -d \
            --name $CONTAINER_NAME \
            --network $NETWORK_NAME \
            -p 9093:9093 \
            -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
            -e TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID" \
            -v "$SCRIPT_DIR/data:/alertmanager" \
            $IMAGE_NAME

        echo -e "${GREEN}Alertmanager started!${NC}"
        echo ""
        echo "Web UI:         http://localhost:9093"
        echo "Alerts:         http://localhost:9093/#/alerts"
        echo "Network:        $NETWORK_NAME"
        echo "Container name: $CONTAINER_NAME"
        echo ""
        echo "Prometheus connects via: $CONTAINER_NAME:9093"
        ;;

    stop)
        echo -e "${YELLOW}Stopping Alertmanager...${NC}"
        docker stop $CONTAINER_NAME 2>/dev/null || true
        docker rm $CONTAINER_NAME 2>/dev/null || true
        echo -e "${GREEN}Stopped!${NC}"
        ;;

    logs)
        docker logs -f $CONTAINER_NAME
        ;;

    status)
        if docker ps | grep -q $CONTAINER_NAME; then
            echo -e "${GREEN}Alertmanager is running${NC}"
            docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
            echo ""
            echo "Active alerts:"
            curl -s http://localhost:9093/api/v2/alerts | python -m json.tool 2>/dev/null || echo "Cannot fetch alerts"
        else
            echo -e "${RED}Alertmanager is not running${NC}"
        fi
        ;;

    test-alert)
        echo -e "${YELLOW}Sending test alert to Alertmanager...${NC}"
        curl -X POST http://localhost:9093/api/v2/alerts \
            -H "Content-Type: application/json" \
            -d '[{
                "labels": {
                    "alertname": "TestFireAlert",
                    "severity": "critical",
                    "device_id": "test_device",
                    "location": "Test Location",
                    "latitude": "21.0285",
                    "longitude": "105.8542"
                },
                "annotations": {
                    "summary": "Test fire alert",
                    "confidence": "0.95"
                }
            }]'
        echo ""
        echo -e "${GREEN}Test alert sent! Check Telegram for notification.${NC}"
        ;;

    *)
        echo "Usage: $0 {build|start|stop|logs|status|test-alert}"
        echo ""
        echo "Commands:"
        echo "  build      - Build Docker image"
        echo "  start      - Start container"
        echo "  stop       - Stop container"
        echo "  logs       - View container logs"
        echo "  status     - Check container status and alerts"
        echo "  test-alert - Send a test alert"
        echo ""
        echo "Environment variables (set in ../.env):"
        echo "  TELEGRAM_BOT_TOKEN"
        echo "  TELEGRAM_CHAT_ID"
        exit 1
        ;;
esac
