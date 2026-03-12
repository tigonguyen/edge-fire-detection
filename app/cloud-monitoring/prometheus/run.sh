#!/bin/bash
# prometheus/run.sh
# Script để chạy Prometheus độc lập

set -e

CONTAINER_NAME="edge-fire-prometheus"
IMAGE_NAME="edge-fire-prometheus"
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
echo -e "${GREEN}     Prometheus Server - Standalone     ${NC}"
echo -e "${GREEN}========================================${NC}"

# Parse arguments
ACTION=${1:-"start"}

# Sử dụng container names trong cùng Docker network
# Không cần dùng host.docker.internal nữa
EXPORTER_TARGET=${EXPORTER_TARGET:-"fire-exporter:8000"}
ALERTMANAGER_TARGET=${ALERTMANAGER_TARGET:-"edge-fire-alertmanager:9093"}

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

        # Create data directory with proper permissions for nobody user (65534)
        mkdir -p "$SCRIPT_DIR/data"
        chmod 777 "$SCRIPT_DIR/data"

        echo -e "${YELLOW}Starting Prometheus...${NC}"
        echo -e "${CYAN}Network: $NETWORK_NAME${NC}"
        echo -e "${CYAN}Scraping from: $EXPORTER_TARGET${NC}"
        echo -e "${CYAN}Alertmanager: $ALERTMANAGER_TARGET${NC}"

        docker run -d \
            --name $CONTAINER_NAME \
            --network $NETWORK_NAME \
            -p 9090:9090 \
            -e EXPORTER_TARGET=$EXPORTER_TARGET \
            -e ALERTMANAGER_TARGET=$ALERTMANAGER_TARGET \
            -v "$SCRIPT_DIR/data:/prometheus" \
            $IMAGE_NAME

        echo -e "${GREEN}Prometheus started!${NC}"
        echo ""
        echo "Web UI:         http://localhost:9090"
        echo "Targets:        http://localhost:9090/targets"
        echo "Alerts:         http://localhost:9090/alerts"
        echo "Network:        $NETWORK_NAME"
        echo "Container name: $CONTAINER_NAME"
        echo ""
        echo "Scraping metrics from: $EXPORTER_TARGET"
        echo ""
        echo "Test queries:"
        echo "  fire_alert_info"
        echo "  fire_alerts_total"
        ;;

    stop)
        echo -e "${YELLOW}Stopping Prometheus...${NC}"
        docker stop $CONTAINER_NAME 2>/dev/null || true
        docker rm $CONTAINER_NAME 2>/dev/null || true
        echo -e "${GREEN}Stopped!${NC}"
        ;;

    logs)
        docker logs -f $CONTAINER_NAME
        ;;

    reload)
        echo -e "${YELLOW}Reloading Prometheus configuration...${NC}"
        curl -X POST http://localhost:9090/-/reload
        echo -e "${GREEN}Configuration reloaded!${NC}"
        ;;

    status)
        if docker ps | grep -q $CONTAINER_NAME; then
            echo -e "${GREEN}Prometheus is running${NC}"
            docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
            echo ""
            echo "Targets status:"
            curl -s http://localhost:9090/api/v1/targets | python -m json.tool 2>/dev/null | grep -A5 '"health"' || echo "Cannot fetch targets"
        else
            echo -e "${RED}Prometheus is not running${NC}"
        fi
        ;;

    query)
        QUERY=${2:-"up"}
        echo -e "${YELLOW}Running query: $QUERY${NC}"
        curl -s "http://localhost:9090/api/v1/query?query=${QUERY}" | python -m json.tool
        ;;

    *)
        echo "Usage: $0 {build|start|stop|logs|reload|status|query}"
        echo ""
        echo "Commands:"
        echo "  build   - Build Docker image"
        echo "  start   - Start container"
        echo "  stop    - Stop container"
        echo "  logs    - View container logs"
        echo "  reload  - Reload configuration"
        echo "  status  - Check container and targets status"
        echo "  query   - Run PromQL query (e.g., ./run.sh query 'fire_alert_info')"
        echo ""
        echo "Environment variables:"
        echo "  EXPORTER_TARGET     - Exporter address (default: host.docker.internal:8000)"
        echo "  ALERTMANAGER_TARGET - Alertmanager address (default: host.docker.internal:9093)"
        exit 1
        ;;
esac
