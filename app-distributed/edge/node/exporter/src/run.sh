#!/bin/bash
# exporter/run.sh
# Script để chạy Fire Detection Exporter độc lập

set -e

CONTAINER_NAME="edge-fire-exporter"
IMAGE_NAME="edge-fire-exporter"
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
echo -e "${GREEN}  Fire Detection Exporter - Standalone  ${NC}"
echo -e "${GREEN}========================================${NC}"

# Parse arguments
ACTION=${1:-"start"}

# Khi trong cùng Docker network, sử dụng container name thay vì host.docker.internal
MQTT_BROKER=${MQTT_BROKER:-"fire-mosquitto"}
MQTT_PORT=${MQTT_PORT:-1883}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-""}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID:-""}

# Fire detection simulation options
# Set SIMULATE_FIRE=true to always detect fire when receiving images (for testing)
# Set SIMULATE_SMOKE=true to always detect smoke when receiving images (for testing)
SIMULATE_FIRE=${SIMULATE_FIRE:-"false"}
SIMULATE_SMOKE=${SIMULATE_SMOKE:-"false"}
FIRE_MODEL_PATH=${FIRE_MODEL_PATH:-""}

# Alert cooldown in seconds (prevent spam from same device+location)
ALERT_COOLDOWN_SECONDS=${ALERT_COOLDOWN_SECONDS:-300}

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

        # Create images directory
        mkdir -p "$PROJECT_DIR/images"

        echo -e "${YELLOW}Starting Exporter...${NC}"
        echo -e "${CYAN}Network: $NETWORK_NAME${NC}"
        echo -e "${CYAN}MQTT Broker: $MQTT_BROKER:$MQTT_PORT${NC}"
        echo -e "${CYAN}SIMULATE_FIRE: $SIMULATE_FIRE${NC}"
        echo -e "${CYAN}SIMULATE_SMOKE: $SIMULATE_SMOKE${NC}"
        echo -e "${CYAN}ALERT_COOLDOWN: ${ALERT_COOLDOWN_SECONDS}s${NC}"

        docker run -d \
            --name $CONTAINER_NAME \
            --network $NETWORK_NAME \
            -p 8000:8000 \
            -e MQTT_BROKER=$MQTT_BROKER \
            -e MQTT_PORT=$MQTT_PORT \
            -e IMAGES_DIR=/app/images \
            -e IMAGE_BASE_URL=http://localhost:8080/images \
            -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
            -e TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID" \
            -e SIMULATE_FIRE="$SIMULATE_FIRE" \
            -e SIMULATE_SMOKE="$SIMULATE_SMOKE" \
            -e FIRE_MODEL_PATH="$FIRE_MODEL_PATH" \
            -e ALERT_COOLDOWN_SECONDS="$ALERT_COOLDOWN_SECONDS" \
            -v "$PROJECT_DIR/images:/app/images" \
            $IMAGE_NAME

        echo -e "${GREEN}Exporter started!${NC}"
        echo ""
        echo "Metrics:        http://localhost:8000/metrics"
        echo "Health:         http://localhost:8000/health"
        echo "Alerts:         http://localhost:8000/alerts"
        echo "Scan History:   http://localhost:8000/scan-history"
        echo "Network:        $NETWORK_NAME"
        echo "Container name: $CONTAINER_NAME"
        echo "SIMULATE_FIRE:  $SIMULATE_FIRE"
        echo "SIMULATE_SMOKE: $SIMULATE_SMOKE"
        echo "ALERT_COOLDOWN: ${ALERT_COOLDOWN_SECONDS}s"
        echo ""
        echo "Connects to MQTT via: $MQTT_BROKER:$MQTT_PORT"
        echo ""
        echo "Test:"
        echo "  curl http://localhost:8000/health"
        echo "  curl -X POST http://localhost:8000/test-alert"
        ;;

    start-local)
        # Run without Docker (for debugging)
        echo -e "${YELLOW}Starting Exporter locally (no Docker)...${NC}"
        echo -e "${CYAN}SIMULATE_FIRE: $SIMULATE_FIRE${NC}"
        echo -e "${CYAN}SIMULATE_SMOKE: $SIMULATE_SMOKE${NC}"
        cd "$SCRIPT_DIR"

        export MQTT_BROKER=localhost
        export MQTT_PORT=1883
        export IMAGES_DIR="$PROJECT_DIR/images"
        export IMAGE_BASE_URL=http://localhost:8080/images
        export SIMULATE_FIRE="$SIMULATE_FIRE"
        export SIMULATE_SMOKE="$SIMULATE_SMOKE"
        export FIRE_MODEL_PATH="$FIRE_MODEL_PATH"
        export ALERT_COOLDOWN_SECONDS="$ALERT_COOLDOWN_SECONDS"

        echo -e "${CYAN}ALERT_COOLDOWN: ${ALERT_COOLDOWN_SECONDS}s${NC}"
        python main.py
        ;;

    stop)
        echo -e "${YELLOW}Stopping Exporter...${NC}"
        docker stop $CONTAINER_NAME 2>/dev/null || true
        docker rm $CONTAINER_NAME 2>/dev/null || true
        echo -e "${GREEN}Stopped!${NC}"
        ;;

    logs)
        docker logs -f $CONTAINER_NAME
        ;;

    shell)
        echo -e "${YELLOW}Opening shell in container...${NC}"
        docker exec -it $CONTAINER_NAME /bin/bash
        ;;

    status)
        if docker ps | grep -q $CONTAINER_NAME; then
            echo -e "${GREEN}Exporter is running${NC}"
            docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
            echo ""
            echo "Quick test:"
            curl -s http://localhost:8000/health | python -m json.tool 2>/dev/null || echo "Cannot connect"
        else
            echo -e "${RED}Exporter is not running${NC}"
        fi
        ;;

    test)
        echo -e "${YELLOW}Sending test alert...${NC}"
        curl -X POST http://localhost:8000/test-alert
        echo ""
        echo -e "${GREEN}Check metrics:${NC}"
        curl -s http://localhost:8000/metrics | grep fire_alert
        ;;

    *)
        echo "Usage: $0 {build|start|start-local|stop|logs|shell|status|test}"
        echo ""
        echo "Commands:"
        echo "  build       - Build Docker image"
        echo "  start       - Start container (Docker)"
        echo "  start-local - Run locally without Docker (for debugging)"
        echo "  stop        - Stop container"
        echo "  logs        - View container logs"
        echo "  shell       - Open shell in container"
        echo "  status      - Check container status"
        echo "  test        - Send test alert"
        echo ""
        echo "Environment variables for fire detection simulation:"
        echo "  SIMULATE_FIRE=true         - Always detect fire (for testing)"
        echo "  SIMULATE_SMOKE=true        - Always detect smoke (for testing)"
        echo "  FIRE_MODEL_PATH=...        - Path to AI model (future use)"
        echo "  ALERT_COOLDOWN_SECONDS=300 - Cooldown in seconds (default 5 min)"
        echo ""
        echo "Examples:"
        echo "  SIMULATE_FIRE=true ./run.sh start"
        echo "  SIMULATE_FIRE=true ./run.sh start-local"
        echo "  SIMULATE_SMOKE=true ./run.sh start"
        echo "  ALERT_COOLDOWN_SECONDS=60 SIMULATE_FIRE=true ./run.sh start"
        exit 1
        ;;
esac
