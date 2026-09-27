#!/usr/bin/env bash
# Forward Prometheus and Grafana ports to localhost for browser access
set -euo pipefail

echo "=================================================================="
echo "⚡ Forwarding Prometheus & Grafana to Localhost"
echo "=================================================================="
echo "• Grafana Dashboard  : http://localhost:3000 (User: admin / admin, or Anonymous)"
echo "• Prometheus Web UI  : http://localhost:9090"
echo "• Direct Dashboard   : http://localhost:3000/d/a550de65-2a30-4cd8-81ff-377ec5c48282/nexus-ai-platform-and-autoscaling-telemetry"
echo "=================================================================="
echo "Press Ctrl+C to terminate port forwarders."

# Launch port-forwarders in parallel
kubectl port-forward -n nexus-monitoring svc/grafana-service 3000:3000 &
PID_GRAFANA=$!

kubectl port-forward -n nexus-monitoring svc/prometheus-service 9090:9090 &
PID_PROM=$!

trap "kill $PID_GRAFANA $PID_PROM 2>/dev/null || true" EXIT INT TERM

wait
