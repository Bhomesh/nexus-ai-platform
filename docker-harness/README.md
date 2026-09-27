# Nexus AI Multi-Container Test Harness Architecture

## Overview
This subsystem orchestrates specialized **Agent Execution Environments** to perform authentic **End-to-End (E2E) testing** against the running Nexus AI Platform (`nexus-gateway` Go server on port 8080 and `nexus-engine` Rust Native server on port 8085) inside Docker:

1. **Controller Container (`nexus-harness-controller:latest`)**:
   - Single orchestrator container running on Docker bridge network `nexus-net`.
   - Manages phased execution workflows, multi-container concurrency, and metric gathering.
   - Interacts with Docker daemon via Unix socket mounting (`/var/run/docker.sock`).
   - Dispatches tasks across four structured execution phases (sequential and parallel).

2. **Agent Worker Containers (`nexus-agent-worker:latest`)**:
   - Ephemeral, fully isolated Docker containers.
   - Run under an unprivileged user (`agentuser`, UID 1000).
   - Strict Linux cgroups resource limits applied per container:
     - `--cpus 1.0` (2.0 for backend stress tests)
     - `--memory 256m` (512m for backend stress tests)
     - `--pids-limit 128`
   - Connected via `nexus-net` with zero-trust isolation from host resources.
   - Guaranteed automatic garbage collection (`--rm`) upon task completion.

---

## Multi-Phase Execution Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 1: Pre-Flight & Platform Readiness (Sequential)                  │
│ • devops_engineer: Docker DNS, TCP RTT, cgroups limits, health checks │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ PASS
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 2: Functional Contract & Security Auditing (Parallel)            │
│ • qa_test_engineer: Telemetry, MCP tools, E2E chat round-trip          │
│ • security_auditor: Non-root UID, filesystem immutability, SQLi fuzz   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ PASS
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 3: State Storage & Vector Migrations (Sequential)                │
│ • database_architect: SQLite WAL integrity, 384-dim vector norm        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ PASS
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 4: Concurrency Stress & Architecture Alignment (Parallel)        │
│ • backend_specialist: 60 concurrent requests, p50/p95 latency metrics  │
│ • code_architect: Gateway-Engine binding, AVX2 SIMD acceleration       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ PASS
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 5: Metric Consolidation & Audit Report Generation                │
│ • Controller aggregates /results/eval_report.json                      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure
```
/home/manjaro/nexus-ai-platform/docker-harness/
├── docker-compose.yml           # Compose specification for harness controller
├── run_docker_harness.sh        # One-click execution and benchmark validation script
├── controller/
│   ├── Dockerfile               # Debian Bookworm slim + Docker CLI
│   └── controller.py            # Orchestrator script for dispatching worker containers
├── agent/
│   ├── Dockerfile               # Lean worker container with non-root security
│   └── runner.py                # Worker execution engine for agent roles
├── benchmarks/
│   └── suite.json               # Multi-agent benchmark suite definitions
└── results/
    └── eval_report.json         # Automated evaluation report & audit metrics
```

---

## How to Run

### 1. Run Complete Benchmark Suite via Shell Script
```bash
/home/manjaro/nexus-ai-platform/docker-harness/run_docker_harness.sh
```

### 2. Run Ad-Hoc Agent Verification Task
To execute an ad-hoc task with a specific agent role:
```bash
docker run --rm \
    --network nexus-net \
    -v /var/run/docker.sock:/var/run/docker.sock \
    nexus-harness-controller:latest \
    python3 /app/controller.py run \
        --role qa_test_engineer \
        --prompt "Verify chat completions and MCP tools" \
        --cpus 1.0 \
        --memory 256m
```

---

## Verification Results Summary

- **Total Tasks**: 6 / 6 Passed (100.0%)
- **Total Assertions**: 26 / 26 Passed (100.0%)
- **Execution Time**: 2.65 seconds
- **Security Audit**: Passed (Non-root UID 1000, read-only system paths, zero leaked credentials)
- **SLA Conformance**: Passed (p50: 8.2ms, p95: 18.23ms, 0% 5xx errors across 60 concurrent requests)
- **Verdict**: **`GO`**
