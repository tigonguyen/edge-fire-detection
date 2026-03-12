#!/bin/bash
# grafana/run.sh
# Script để chạy Grafana độc lập

set -e

CONTAINER_NAME="edge-fire-grafana"
IMAGE_NAME="edge-fire-grafana"
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

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}    Grafana Dashboard - Standalone      ${NC}"
echo -e "${GREEN}========================================${NC}"

# Parse arguments
ACTION=${1:-"start"}

# Sử dụng container names trong cùng Docker network
PROMETHEUS_URL=${PROMETHEUS_URL:-"http://edge-fire-prometheus:9090"}
ALERTMANAGER_URL=${ALERTMANAGER_URL:-"http://edge-fire-alertmanager:9093"}
ADMIN_USER=${GF_SECURITY_ADMIN_USER:-"admin"}
ADMIN_PASSWORD=${GF_SECURITY_ADMIN_PASSWORD:-"admin123"}

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

        # Create data directory with proper permissions for grafana user (472)
        mkdir -p "$SCRIPT_DIR/data"
        chmod 777 "$SCRIPT_DIR/data"

        echo -e "${YELLOW}Starting Grafana...${NC}"
        echo -e "${CYAN}Network: $NETWORK_NAME${NC}"
        echo -e "${CYAN}Prometheus: $PROMETHEUS_URL${NC}"
        echo -e "${CYAN}Alertmanager: $ALERTMANAGER_URL${NC}"

        docker run -d \
            --name $CONTAINER_NAME \
            --network $NETWORK_NAME \
            -p 3000:3000 \
            -e GF_SECURITY_ADMIN_USER=$ADMIN_USER \
            -e GF_SECURITY_ADMIN_PASSWORD=$ADMIN_PASSWORD \
            -e PROMETHEUS_URL=$PROMETHEUS_URL \
            -e ALERTMANAGER_URL=$ALERTMANAGER_URL \
            -v "$SCRIPT_DIR/data:/var/lib/grafana" \
            -v "$PROJECT_DIR/images:/var/lib/grafana/images:ro" \
            $IMAGE_NAME

        echo -e "${GREEN}Grafana started!${NC}"
        echo ""
        echo "Dashboard:      http://localhost:3000"
        echo "Login:          $ADMIN_USER / $ADMIN_PASSWORD"
        echo "Network:        $NETWORK_NAME"
        echo "Container name: $CONTAINER_NAME"
        echo ""
        echo "Connects to Prometheus: $PROMETHEUS_URL"
        echo ""
        echo "Pre-configured dashboards:"
        echo "  - Fire Detection Dashboard (with Geomap)"
        ;;

    stop)
        echo -e "${YELLOW}Stopping Grafana...${NC}"
        docker stop $CONTAINER_NAME 2>/dev/null || true
        docker rm $CONTAINER_NAME 2>/dev/null || true
        echo -e "${GREEN}Stopped!${NC}"
        ;;

    logs)
        docker logs -f $CONTAINER_NAME
        ;;

    status)
        if docker ps | grep -q $CONTAINER_NAME; then
            echo -e "${GREEN}Grafana is running${NC}"
            docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
            echo ""
            echo "Health check:"
            curl -s http://localhost:3000/api/health | python -m json.tool 2>/dev/null || echo "Cannot connect"
        else
            echo -e "${RED}Grafana is not running${NC}"
        fi
        ;;

    reset-password)
        NEW_PASSWORD=${2:-"admin123"}
        echo -e "${YELLOW}Resetting admin password...${NC}"
        docker exec -it $CONTAINER_NAME grafana-cli admin reset-admin-password $NEW_PASSWORD
        echo -e "${GREEN}Password reset to: $NEW_PASSWORD${NC}"
        ;;

    *)
        echo "Usage: $0 {build|start|stop|logs|status|reset-password}"
        echo ""
        echo "Commands:"
        echo "  build          - Build Docker image"
        echo "  start          - Start container"
        echo "  stop           - Stop container"
        echo "  logs           - View container logs"
        echo "  status         - Check container status"
        echo "  reset-password - Reset admin password"
        echo ""
        echo "Environment variables:"
        echo "  PROMETHEUS_URL          - Prometheus address (default: http://host.docker.internal:9090)"
        echo "  ALERTMANAGER_URL        - Alertmanager address (default: http://host.docker.internal:9093)"
        echo "  GF_SECURITY_ADMIN_USER  - Admin username (default: admin)"
        echo "  GF_SECURITY_ADMIN_PASSWORD - Admin password (default: admin123)"
        exit 1
        ;;
esac
