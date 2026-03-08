#!/bin/bash
# run-all.sh
# Master script để quản lý tất cả services
# Hỗ trợ chạy từng service độc lập hoặc tất cả cùng lúc

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ==========================================
# SHARED DOCKER NETWORK
# Tất cả containers sẽ join vào network này
# để có thể communicate với nhau
# ==========================================
NETWORK_NAME="fire-detection-network"
export NETWORK_NAME

# Services list (theo thứ tự khởi động)
SERVICES=("mosquitto" "nginx" "exporter" "prometheus" "alertmanager" "grafana")

# Tạo shared network nếu chưa có
create_network() {
    if ! docker network inspect $NETWORK_NAME >/dev/null 2>&1; then
        echo -e "${YELLOW}Creating shared Docker network: $NETWORK_NAME${NC}"
        docker network create $NETWORK_NAME
        echo -e "${GREEN}Network created!${NC}"
    else
        echo -e "${GREEN}Network $NETWORK_NAME already exists${NC}"
    fi
}

print_header() {
    echo -e "${GREEN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║       Fire Detection Monitoring System - Service Manager       ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_usage() {
    echo "Usage: $0 <command> [service]"
    echo ""
    echo "Commands:"
    echo "  start [service]    - Start service(s)"
    echo "  stop [service]     - Stop service(s)"
    echo "  restart [service]  - Restart service(s)"
    echo "  status             - Show status of all services"
    echo "  logs <service>     - View logs for a service"
    echo "  build [service]    - Build Docker image(s)"
    echo "  network            - Create/check shared Docker network"
    echo "  clean              - Stop all and remove containers/images/network"
    echo ""
    echo "Services:"
    echo "  mosquitto    - MQTT Broker (port 1883, 9001)"
    echo "  nginx        - Image Server (port 8080)"
    echo "  exporter     - Prometheus Exporter (port 8000)"
    echo "  prometheus   - Prometheus Server (port 9090)"
    echo "  alertmanager - Alertmanager (port 9093)"
    echo "  grafana      - Grafana Dashboard (port 3000)"
    echo "  all          - All services"
    echo ""
    echo "Examples:"
    echo "  $0 start all           # Start all services"
    echo "  $0 start mosquitto     # Start only MQTT broker"
    echo "  $0 stop grafana        # Stop only Grafana"
    echo "  $0 status              # Check all services status"
    echo "  $0 logs exporter       # View exporter logs"
}

run_service_script() {
    local service=$1
    local action=$2
    local script="$SCRIPT_DIR/$service/run.sh"

    if [ -f "$script" ]; then
        chmod +x "$script"
        # Pass NETWORK_NAME to child scripts
        NETWORK_NAME=$NETWORK_NAME "$script" "$action"
    else
        echo -e "${RED}Script not found: $script${NC}"
        return 1
    fi
}

start_service() {
    local service=$1
    echo -e "${YELLOW}Starting $service...${NC}"
    run_service_script "$service" "start"
    echo ""
}

stop_service() {
    local service=$1
    echo -e "${YELLOW}Stopping $service...${NC}"
    run_service_script "$service" "stop"
    echo ""
}

build_service() {
    local service=$1
    echo -e "${YELLOW}Building $service...${NC}"
    run_service_script "$service" "build"
    echo ""
}

start_all() {
    echo -e "${CYAN}Starting all services in order...${NC}"
    echo ""

    # Tạo network trước khi start services
    create_network

    for service in "${SERVICES[@]}"; do
        start_service "$service"
        sleep 2  # Wait a bit between services
    done

    echo -e "${GREEN}All services started!${NC}"
    show_status
}

stop_all() {
    echo -e "${CYAN}Stopping all services...${NC}"
    echo ""

    # Stop in reverse order
    for ((i=${#SERVICES[@]}-1; i>=0; i--)); do
        stop_service "${SERVICES[$i]}"
    done

    echo -e "${GREEN}All services stopped!${NC}"
}

build_all() {
    echo -e "${CYAN}Building all Docker images...${NC}"
    echo ""

    for service in "${SERVICES[@]}"; do
        build_service "$service"
    done

    echo -e "${GREEN}All images built!${NC}"
}

show_status() {
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                        Service Status                          ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Check network status
    if docker network inspect $NETWORK_NAME >/dev/null 2>&1; then
        echo -e "Docker Network: ${GREEN}$NETWORK_NAME (active)${NC}"
    else
        echo -e "Docker Network: ${RED}$NETWORK_NAME (not created)${NC}"
    fi
    echo ""

    printf "%-15s %-10s %-30s\n" "SERVICE" "STATUS" "URL"
    echo "─────────────────────────────────────────────────────────────"

    # Check each service
    check_service "mosquitto" "fire-mosquitto" "localhost:1883 (MQTT)"
    check_service "nginx" "fire-nginx" "http://localhost:8080/images/"
    check_service "exporter" "fire-exporter" "http://localhost:8000/metrics"
    check_service "prometheus" "fire-prometheus" "http://localhost:9090"
    check_service "alertmanager" "fire-alertmanager" "http://localhost:9093"
    check_service "grafana" "fire-grafana" "http://localhost:3000"

    echo ""
    echo -e "${CYAN}Quick Links:${NC}"
    echo "  Grafana Dashboard: http://localhost:3000 (admin/admin123)"
    echo "  Prometheus:        http://localhost:9090"
    echo "  Alertmanager:      http://localhost:9093"
    echo "  Exporter Metrics:  http://localhost:8000/metrics"
    echo ""
    echo -e "${CYAN}Inter-container Communication (inside network):${NC}"
    echo "  MQTT:        fire-mosquitto:1883"
    echo "  Exporter:    fire-exporter:8000"
    echo "  Prometheus:  fire-prometheus:9090"
    echo "  Alertmanager: fire-alertmanager:9093"
}

check_service() {
    local name=$1
    local container=$2
    local url=$3

    if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
        printf "%-15s ${GREEN}%-10s${NC} %-30s\n" "$name" "RUNNING" "$url"
    else
        printf "%-15s ${RED}%-10s${NC} %-30s\n" "$name" "STOPPED" "-"
    fi
}

show_logs() {
    local service=$1
    local container="fire-$service"

    echo -e "${CYAN}Showing logs for $service...${NC}"
    docker logs -f "$container"
}

clean_all() {
    echo -e "${RED}WARNING: This will stop and remove all containers, images, and network!${NC}"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        stop_all

        echo -e "${YELLOW}Removing containers...${NC}"
        for service in "${SERVICES[@]}"; do
            docker rm "fire-$service" 2>/dev/null || true
        done

        echo -e "${YELLOW}Removing images...${NC}"
        for service in "${SERVICES[@]}"; do
            docker rmi "fire-$service" 2>/dev/null || true
        done

        echo -e "${YELLOW}Removing network...${NC}"
        docker network rm $NETWORK_NAME 2>/dev/null || true

        echo -e "${GREEN}Cleanup complete!${NC}"
    else
        echo "Cancelled."
    fi
}

# Main
print_header

ACTION=${1:-"help"}
SERVICE=${2:-"all"}

case $ACTION in
    start)
        # Luôn tạo network trước khi start bất kỳ service nào
        create_network
        if [ "$SERVICE" == "all" ]; then
            start_all
        else
            start_service "$SERVICE"
        fi
        ;;

    network)
        create_network
        echo ""
        echo "Containers in network:"
        docker network inspect $NETWORK_NAME --format '{{range .Containers}}  - {{.Name}}{{"\n"}}{{end}}' 2>/dev/null || echo "  (none)"
        ;;

    stop)
        if [ "$SERVICE" == "all" ]; then
            stop_all
        else
            stop_service "$SERVICE"
        fi
        ;;

    restart)
        if [ "$SERVICE" == "all" ]; then
            stop_all
            start_all
        else
            stop_service "$SERVICE"
            sleep 1
            start_service "$SERVICE"
        fi
        ;;

    build)
        if [ "$SERVICE" == "all" ]; then
            build_all
        else
            build_service "$SERVICE"
        fi
        ;;

    status)
        show_status
        ;;

    logs)
        if [ -z "$SERVICE" ] || [ "$SERVICE" == "all" ]; then
            echo "Please specify a service: $0 logs <service>"
            exit 1
        fi
        show_logs "$SERVICE"
        ;;

    clean)
        clean_all
        ;;

    help|--help|-h|*)
        print_usage
        ;;
esac
