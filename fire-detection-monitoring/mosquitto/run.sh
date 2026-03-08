#!/bin/bash
# mosquitto/run.sh
# Script để chạy Mosquitto MQTT Broker độc lập

set -e

CONTAINER_NAME="fire-mosquitto"
IMAGE_NAME="fire-mosquitto"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Shared Docker network - cho phép các containers communicate với nhau
NETWORK_NAME=${NETWORK_NAME:-"fire-detection-network"}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Tạo network nếu chưa có
ensure_network() {
    if ! docker network inspect $NETWORK_NAME >/dev/null 2>&1; then
        echo -e "${YELLOW}Creating network: $NETWORK_NAME${NC}"
        docker network create $NETWORK_NAME
    fi
}

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  MQTT Broker (Mosquitto) - Standalone  ${NC}"
echo -e "${GREEN}========================================${NC}"

# Parse arguments
ACTION=${1:-"start"}

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

        # Create data directories
        mkdir -p "$SCRIPT_DIR/data" "$SCRIPT_DIR/log"

        echo -e "${YELLOW}Starting Mosquitto...${NC}"
        docker run -d \
            --name $CONTAINER_NAME \
            --network $NETWORK_NAME \
            -p 1883:1883 \
            -p 9001:9001 \
            -v "$SCRIPT_DIR/data:/mosquitto/data" \
            -v "$SCRIPT_DIR/log:/mosquitto/log" \
            $IMAGE_NAME

        echo -e "${GREEN}Mosquitto started!${NC}"
        echo ""
        echo "MQTT Port:      localhost:1883"
        echo "WebSocket Port: localhost:9001"
        echo "Network:        $NETWORK_NAME"
        echo "Container name: $CONTAINER_NAME"
        echo ""
        echo "Other containers connect via: $CONTAINER_NAME:1883"
        echo ""
        echo "Test commands:"
        echo "  Subscribe: mosquitto_sub -h localhost -t 'wildfire/#' -v"
        echo "  Publish:   mosquitto_pub -h localhost -t 'wildfire/test' -m 'hello'"
        ;;

    stop)
        echo -e "${YELLOW}Stopping Mosquitto...${NC}"
        docker stop $CONTAINER_NAME 2>/dev/null || true
        docker rm $CONTAINER_NAME 2>/dev/null || true
        echo -e "${GREEN}Stopped!${NC}"
        ;;

    logs)
        docker logs -f $CONTAINER_NAME
        ;;

    status)
        if docker ps | grep -q $CONTAINER_NAME; then
            echo -e "${GREEN}Mosquitto is running${NC}"
            docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        else
            echo -e "${RED}Mosquitto is not running${NC}"
        fi
        ;;

    *)
        echo "Usage: $0 {build|start|stop|logs|status}"
        exit 1
        ;;
esac
