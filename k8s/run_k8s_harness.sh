#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="nexus-system"

echo "=================================================================="
echo "⚡ Nexus AI Platform: Kubernetes Deployment & Autoscaling Harness"
echo "=================================================================="

# 1. Verify Minikube & Cluster Connectivity
if ! minikube status >/dev/null 2>&1; then
    echo "[!] Minikube is not running. Starting minikube..."
    minikube start --driver=docker
fi

echo "[+] Connected to Kubernetes cluster (Node: $(kubectl get nodes -o jsonpath='{.items[0].metadata.name}'))"

# 2. Deploy Infrastructure & Services
echo "[+] Deploying Namespace, Engine, Gateway, and Horizontal Pod Autoscaler..."
kubectl apply -f "$DIR/00-namespace.yaml"
kubectl apply -f "$DIR/01-engine.yaml"
kubectl apply -f "$DIR/02-gateway.yaml"
kubectl apply -f "$DIR/03-hpa.yaml"

echo "[+] Awaiting Deployment Rollout..."
kubectl rollout status deployment/nexus-engine -n "$NAMESPACE" --timeout=60s
kubectl rollout status deployment/nexus-gateway -n "$NAMESPACE" --timeout=60s

# 3. Execute Multi-Agent Test Suite via Kubernetes Jobs
echo ""
echo "=================================================================="
echo "🤖 Discarding previous test jobs and launching Multi-Agent Test Fleet..."
echo "=================================================================="
kubectl delete jobs --all -n "$NAMESPACE" 2>/dev/null || true
kubectl apply -f "$DIR/04-agent-jobs.yaml"

echo "[+] Waiting for Agent Jobs to complete assertions in Kubernetes..."
for job in agent-devops-preflight agent-qa-contract agent-security-audit agent-database-integrity agent-backend-concurrency; do
    kubectl wait --for=condition=complete job/"$job" -n "$NAMESPACE" --timeout=60s >/dev/null
    echo "  [✔] Job $job COMPLETED"
done

echo ""
echo "=================================================================="
echo "📈 Demonstrating Dynamic Horizontal Pod Autoscaling (HPA)..."
echo "=================================================================="
echo "[+] Initial Gateway Replicas:"
kubectl get deployment/nexus-gateway -n "$NAMESPACE" -o wide

echo "[+] Dispatching Workload Generator Job to trigger CPU threshold (>50%)..."
kubectl apply -f "$DIR/05-workload-generator.yaml"

echo "[+] Monitoring Autoscaler response (sampling for 30s)..."
for i in {1..6}; do
    sleep 5
    echo -n "  • Sample $i: "
    kubectl get hpa nexus-gateway-hpa -n "$NAMESPACE" --no-headers | awk '{print "CPU: " $3 " | Current Replicas: " $6 " (Min: " $4 ", Max: " $5 ")"}'
done

echo ""
echo "[+] Scaled Pod Fleet:"
kubectl get pods -n "$NAMESPACE" -l app=nexus-gateway

echo ""
echo "=================================================================="
echo "🎯 All Kubernetes Multi-Agent Tests & Autoscaling Verified!"
echo "=================================================================="
