#!/usr/bin/env bash
set -euo pipefail

# Directory of this script
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=================================================================="
echo "⚡ Nexus AI Platform: Multi-Agent Containerized E2E Testing"
echo "=================================================================="
echo "[+] Target Docker Network: nexus-net"

# Ensure target network exists
if ! docker network inspect nexus-net >/dev/null 2>&1; then
    echo "[+] Creating Docker network: nexus-net"
    docker network create nexus-net
fi

# 1. Build Worker Agent Image
echo "[+] [1/3] Building Agent Worker Image (nexus-agent-worker:latest)..."
docker build -t nexus-agent-worker:latest "$DIR/agent"

# 2. Build Controller Image
echo "[+] [2/3] Building Controller Image (nexus-harness-controller:latest)..."
docker build -t nexus-harness-controller:latest "$DIR/controller"

# 3. Execute End-to-End Suite
echo "[+] [3/3] Launching Controller Container with phased multi-agent execution..."
mkdir -p "$DIR/results"

docker run --rm \
    --name nexus-harness-controller-run \
    --network nexus-net \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$DIR/benchmarks:/benchmarks:ro" \
    -v "$DIR/results:/results:rw" \
    -e PYTHONUNBUFFERED=1 \
    nexus-harness-controller:latest \
    python3 /app/controller.py eval --network nexus-net --suite /benchmarks/suite.json --output /results/eval_report.json

echo ""
echo "=================================================================="
echo "🎯 Execution Complete! Summary of generated report:"
echo "=================================================================="
if [ -f "$DIR/results/eval_report.json" ]; then
    cat "$DIR/results/eval_report.json" | jq '{metadata, summary, verdict}'
fi
echo ""
