#!/usr/bin/env bash
# Nexus AI Platform Control & Daemon Supervisor

BASE_DIR="/home/manjaro/nexus-ai-platform"
ENGINE_BIN="$BASE_DIR/engine-rust/target/release/nexus-engine"
GATEWAY_BIN="$BASE_DIR/gateway-go/bin/nexus-gateway"
PID_DIR="$BASE_DIR/data"
mkdir -p "$PID_DIR"

start_services() {
    echo "[+] Starting Nexus AI Platform..."

    # 1. Start Rust Engine (Port 8085)
    if [ -f "$PID_DIR/engine.pid" ] && kill -0 "$(cat "$PID_DIR/engine.pid")" 2>/dev/null; then
        echo "    • Rust Engine already running (PID $(cat "$PID_DIR/engine.pid"))"
    else
        echo "    • Launching Rust Inference Engine on http://127.0.0.1:8085..."
        nohup "$ENGINE_BIN" > "$PID_DIR/engine.log" 2>&1 &
        echo $! > "$PID_DIR/engine.pid"
        disown
    fi

    # 2. Start Go Gateway (Port 8080)
    if [ -f "$PID_DIR/gateway.pid" ] && kill -0 "$(cat "$PID_DIR/gateway.pid")" 2>/dev/null; then
        echo "    • Go Gateway already running (PID $(cat "$PID_DIR/gateway.pid"))"
    else
        echo "    • Launching Go Concurrency Gateway on http://127.0.0.1:8080..."
        nohup "$GATEWAY_BIN" > "$PID_DIR/gateway.log" 2>&1 &
        echo $! > "$PID_DIR/gateway.pid"
        disown
    fi

    sleep 1
    echo "[✔] All services started successfully!"
    echo "    • Web Dashboard : http://127.0.0.1:8080"
    echo "    • Rust Engine   : http://127.0.0.1:8085/health"
}

stop_services() {
    echo "[-] Stopping Nexus AI Platform..."
    if [ -f "$PID_DIR/engine.pid" ]; then
        PID=$(cat "$PID_DIR/engine.pid")
        kill "$PID" 2>/dev/null && echo "    • Stopped Rust Engine (PID $PID)"
        rm -f "$PID_DIR/engine.pid"
    fi
    if [ -f "$PID_DIR/gateway.pid" ]; then
        PID=$(cat "$PID_DIR/gateway.pid")
        kill "$PID" 2>/dev/null && echo "    • Stopped Go Gateway (PID $PID)"
        rm -f "$PID_DIR/gateway.pid"
    fi
}

status_services() {
    echo "=== Nexus AI Platform Status ==="
    if [ -f "$PID_DIR/engine.pid" ] && kill -0 "$(cat "$PID_DIR/engine.pid")" 2>/dev/null; then
        echo "  • Rust Engine   : RUNNING (PID $(cat "$PID_DIR/engine.pid")) on Port 8085"
    else
        echo "  • Rust Engine   : STOPPED"
    fi

    if [ -f "$PID_DIR/gateway.pid" ] && kill -0 "$(cat "$PID_DIR/gateway.pid")" 2>/dev/null; then
        echo "  • Go Gateway    : RUNNING (PID $(cat "$PID_DIR/gateway.pid")) on Port 8080"
    else
        echo "  • Go Gateway    : STOPPED"
    fi

    echo ""
    curl -s http://127.0.0.1:8080/api/telemetry 2>/dev/null | grep -o '"{.*}"' || curl -s http://127.0.0.1:8080/api/telemetry 2>/dev/null
    echo ""
}

case "$1" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        sleep 1
        start_services
        ;;
    status)
        status_services
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
