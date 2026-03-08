#!/bin/bash
# nginx/run.sh
# Script để chạy Nginx Image Server độc lập

set -e

CONTAINER_NAME="fire-nginx"
IMAGE_NAME="fire-nginx"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Shared Docker network
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
echo -e "${GREEN}   Nginx Image Server - Standalone      ${NC}"
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

        # Create images directory
        mkdir -p "$PROJECT_DIR/images"

        echo -e "${YELLOW}Starting Nginx...${NC}"

        docker run -d \
            --name $CONTAINER_NAME \
            --network $NETWORK_NAME \
            -p 8080:80 \
            -v "$PROJECT_DIR/images:/usr/share/nginx/html/images:ro" \
            $IMAGE_NAME

        echo -e "${GREEN}Nginx started!${NC}"
        echo ""
        echo "Images URL:     http://localhost:8080/images/"
        echo "Network:        $NETWORK_NAME"
        echo "Container name: $CONTAINER_NAME"
        echo ""
        echo "Test:"
        echo "  curl http://localhost:8080/images/"
        ;;

    stop)
        echo -e "${YELLOW}Stopping Nginx...${NC}"
        docker stop $CONTAINER_NAME 2>/dev/null || true
        docker rm $CONTAINER_NAME 2>/dev/null || true
        echo -e "${GREEN}Stopped!${NC}"
        ;;

    logs)
        docker logs -f $CONTAINER_NAME
        ;;

    status)
        if docker ps | grep -q $CONTAINER_NAME; then
            echo -e "${GREEN}Nginx is running${NC}"
            docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
            echo ""
            echo "Images in directory:"
            ls -la "$PROJECT_DIR/images/" 2>/dev/null | head -10 || echo "No images yet"
        else
            echo -e "${RED}Nginx is not running${NC}"
        fi
        ;;

    *)
        echo "Usage: $0 {build|start|stop|logs|status}"
        echo ""
        echo "Commands:"
        echo "  build   - Build Docker image"
        echo "  start   - Start container"
        echo "  stop    - Stop container"
        echo "  logs    - View container logs"
        echo "  status  - Check container status and list images"
        exit 1
        ;;
esac
