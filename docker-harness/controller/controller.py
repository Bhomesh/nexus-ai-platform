#!/usr/bin/env python3
"""
Nexus AI Platform - Multi-Container Harness Controller.
Orchestrates isolated Agent Worker containers on Docker network 'nexus-net'.
Implements phased multi-agent E2E execution, metrics aggregation, and audit reporting.
"""

import sys
import os
import json
import time
import subprocess
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

DOCKER_IMAGE_AGENT = "nexus-agent-worker:latest"
DEFAULT_NETWORK = "nexus-net"
DEFAULT_GATEWAY_URL = "http://nexus-gateway:8080"
DEFAULT_ENGINE_URL = "http://nexus-engine:8085"

class HarnessController:
    def __init__(self,
                 agent_image: str = DOCKER_IMAGE_AGENT,
                 network_name: str = DEFAULT_NETWORK,
                 gateway_url: str = DEFAULT_GATEWAY_URL,
                 engine_url: str = DEFAULT_ENGINE_URL):
        self.agent_image = agent_image
        self.network_name = network_name
        self.gateway_url = gateway_url
        self.engine_url = engine_url
        self._ensure_network()

    def _ensure_network(self):
        """Ensures the target Docker bridge network exists."""
        check = subprocess.run(["docker", "network", "inspect", self.network_name], capture_output=True)
        if check.returncode != 0:
            print(f"[+] Creating Docker bridge network: {self.network_name}")
            subprocess.run(["docker", "network", "create", self.network_name], check=True)
        else:
            print(f"[✔] Docker network active: {self.network_name}")

    def run_agent_task(self, task_name: str, agent_role: str, prompt: str, cpus: float = 1.0, memory_limit: str = "256m") -> dict:
        """
        Spawns an ephemeral, isolated Agent Worker container on the network,
        captures stdout/stderr and structured metrics, and tears it down cleanly.
        """
        container_name = f"agent-{agent_role.replace('_', '-')}-{int(time.time()*1000)%100000}"
        print(f"\n==================================================================")
        print(f"[*] Spawning Agent Worker: [{task_name}]")
        print(f"    • Role             : {agent_role}")
        print(f"    • Target Container : {container_name}")
        print(f"    • Network Bridge   : {self.network_name}")
        print(f"    • Resource Limits  : {cpus} CPUs, {memory_limit} RAM")
        print(f"    • Gateway Endpoint : {self.gateway_url}")
        print(f"==================================================================")

        start_time = time.time()

        cmd = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--network", self.network_name,
            f"--cpus={cpus}",
            f"--memory={memory_limit}",
            f"--memory-swap={memory_limit}",
            "--pids-limit=128",
            "-e", f"AGENT_ROLE={agent_role}",
            "-e", f"AGENT_TASK={prompt}",
            "-e", f"TARGET_GATEWAY_URL={self.gateway_url}",
            "-e", f"TARGET_ENGINE_URL={self.engine_url}",
            self.agent_image
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            elapsed = round(time.time() - start_time, 3)

            # Extract structured result JSON
            parsed_json = {}
            for line in reversed(res.stdout.splitlines()):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        parsed_json = json.loads(line)
                        break
                    except Exception:
                        pass
            if not parsed_json and "{" in res.stdout:
                try:
                    start_idx = res.stdout.find("{")
                    end_idx = res.stdout.rfind("}") + 1
                    if start_idx != -1 and end_idx > start_idx:
                        parsed_json = json.loads(res.stdout[start_idx:end_idx])
                except Exception:
                    pass

            assertions = parsed_json.get("assertions", [])
            metrics = parsed_json.get("metrics", {})
            passed_assertions = sum(1 for a in assertions if a.get("passed"))
            success = res.returncode == 0 and parsed_json.get("status") == "SUCCESS"

            status_label = "[PASS]" if success else "[FAIL]"
            print(f"{status_label} {agent_role} finished in {elapsed}s ({passed_assertions}/{len(assertions)} assertions passed)")

            return {
                "task_name": task_name,
                "agent_role": agent_role,
                "container_id": container_name,
                "cgroup_limits": {
                    "cpus": cpus,
                    "memory": memory_limit
                },
                "exit_code": res.returncode,
                "elapsed_seconds": elapsed,
                "status": "PASSED" if success else "FAILED",
                "assertions": assertions,
                "metrics": metrics,
                "error_details": res.stderr if not success else None,
                "raw_stdout": res.stdout
            }

        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
            return {
                "task_name": task_name,
                "agent_role": agent_role,
                "container_id": container_name,
                "cgroup_limits": {"cpus": cpus, "memory": memory_limit},
                "exit_code": -1,
                "elapsed_seconds": 90.0,
                "status": "FAILED",
                "assertions": [],
                "metrics": {},
                "error_details": "Execution timed out (90s limit exceeded)"
            }

    def run_e2e_benchmark_suite(self, suite_path: str, output_report_path: str = "/results/eval_report.json"):
        """
        Executes phased multi-agent E2E benchmark pipeline:
        - Phase 1: Pre-Flight & Readiness (devops_engineer)
        - Phase 2: Functional API & Security Audit (qa_test_engineer, security_auditor)
        - Phase 3: State Storage & Vector Migrations (database_architect)
        - Phase 4: High-Concurrency Load & Architecture Alignment (backend_specialist, code_architect)
        """
        with open(suite_path, "r") as f:
            suite_data = json.load(f)

        print("\n==================================================================")
        print("⚡ Nexus AI Multi-Agent Containerized E2E Test Suite")
        print(f"[*] Target Network: {self.network_name}")
        print(f"[*] Gateway       : {self.gateway_url}")
        print(f"[*] Engine        : {self.engine_url}")
        print(f"[*] Benchmark Plan: {len(suite_data)} tasks across phased execution")
        print("==================================================================")

        suite_start = time.time()
        tasks_by_id = {item.get("id", f"TASK-{idx}"): item for idx, item in enumerate(suite_data, 1)}

        # Define 4 execution phases
        phases_def = [
            {
                "phase_id": "phase_1_preflight_readiness",
                "name": "Phase 1: Pre-Flight & Platform Readiness",
                "mode": "sequential",
                "task_ids": ["OPS-001"]
            },
            {
                "phase_id": "phase_2_functional_and_security",
                "name": "Phase 2: Functional Contract & Security Auditing",
                "mode": "parallel",
                "task_ids": ["QA-001", "SEC-001"]
            },
            {
                "phase_id": "phase_3_state_and_schema",
                "name": "Phase 3: State Storage & Vector Schema Migrations",
                "mode": "sequential",
                "task_ids": ["DB-001"]
            },
            {
                "phase_id": "phase_4_concurrency_and_architecture",
                "name": "Phase 4: Concurrency Stress & Architecture Alignment",
                "mode": "parallel",
                "task_ids": ["BE-001", "ARCH-001"]
            }
        ]

        executed_phases = []
        total_assertions = 0
        passed_assertions = 0
        all_agents_results = []

        for phase in phases_def:
            phase_id = phase["phase_id"]
            phase_name = phase["name"]
            mode = phase["mode"]
            t_ids = [tid for tid in phase["task_ids"] if tid in tasks_by_id]
            if not t_ids:
                continue

            print(f"\n>>> Starting {phase_name} [Mode: {mode.upper()}] <<<")
            phase_agents = []

            if mode == "parallel" and len(t_ids) > 1:
                with ThreadPoolExecutor(max_workers=len(t_ids)) as executor:
                    future_to_task = {}
                    for tid in t_ids:
                        t = tasks_by_id[tid]
                        cpus = t.get("cpus", 2.0 if "backend" in t.get("role", "") else 1.0)
                        mem = t.get("memory", "512m" if "backend" in t.get("role", "") else "256m")
                        fut = executor.submit(self.run_agent_task, t["name"], t["role"], t["prompt"], cpus, mem)
                        future_to_task[fut] = t

                    for fut in as_completed(future_to_task):
                        res = fut.result()
                        phase_agents.append(res)
                        all_agents_results.append(res)
            else:
                for tid in t_ids:
                    t = tasks_by_id[tid]
                    cpus = t.get("cpus", 2.0 if "backend" in t.get("role", "") else 1.0)
                    mem = t.get("memory", "512m" if "backend" in t.get("role", "") else "256m")
                    res = self.run_agent_task(t["name"], t["role"], t["prompt"], cpus, mem)
                    phase_agents.append(res)
                    all_agents_results.append(res)

            for a in phase_agents:
                for asrt in a.get("assertions", []):
                    total_assertions += 1
                    if asrt.get("passed"):
                        passed_assertions += 1

            executed_phases.append({
                "phase_id": phase_id,
                "execution_mode": mode,
                "agents": phase_agents
            })

            # Check if critical preflight phase failed
            if phase_id == "phase_1_preflight_readiness":
                if any(a["status"] == "FAILED" for a in phase_agents):
                    print("[-] Critical Pre-Flight phase failed. Aborting subsequent phases.")
                    break

        total_duration = round(time.time() - suite_start, 2)
        total_tasks = len(all_agents_results)
        tasks_passed = sum(1 for a in all_agents_results if a["status"] == "PASSED")
        tasks_failed = total_tasks - tasks_passed
        pass_rate = round((tasks_passed / total_tasks * 100), 1) if total_tasks > 0 else 0.0

        # Assess security and SLA gates
        sec_agent = next((a for a in all_agents_results if a["agent_role"] == "security_auditor"), None)
        security_passed = bool(sec_agent and sec_agent["status"] == "PASSED")

        be_agent = next((a for a in all_agents_results if a["agent_role"] == "backend_specialist"), None)
        sla_compliant = False
        if be_agent and be_agent.get("metrics"):
            p95 = be_agent["metrics"].get("p95_latency_ms", 999)
            errs = be_agent["metrics"].get("error_count", 999)
            sla_compliant = p95 < 50.0 and errs == 0

        verdict_status = "GO" if tasks_failed == 0 and security_passed and sla_compliant else "NO_GO"
        blockers = []
        if tasks_failed > 0:
            blockers.append(f"{tasks_failed} agent task(s) failed assertions")
        if not security_passed:
            blockers.append("Security audit criteria not met")
        if not sla_compliant:
            blockers.append("Backend latency or error rate SLA violated")

        report = {
            "metadata": {
                "execution_id": f"nexus-e2e-{int(time.time())}",
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "docker_network": self.network_name,
                "gateway_url": self.gateway_url,
                "engine_url": self.engine_url,
                "host_hardware": {
                    "cpu_model": "AMD Ryzen 7 5800H with Radeon Graphics",
                    "hardware_threads": 16,
                    "gpu_model": "NVIDIA GeForce RTX 3060 Mobile"
                }
            },
            "summary": {
                "total_tasks": total_tasks,
                "passed": tasks_passed,
                "failed": tasks_failed,
                "pass_rate_percent": pass_rate,
                "total_assertions": total_assertions,
                "passed_assertions": passed_assertions,
                "assertion_pass_rate_percent": round((passed_assertions / total_assertions * 100), 1) if total_assertions > 0 else 0.0,
                "total_duration_seconds": total_duration,
                "sla_compliant": sla_compliant,
                "security_passed": security_passed
            },
            "phases": executed_phases,
            "verdict": {
                "status": verdict_status,
                "blockers": blockers,
                "recommendations": [
                    "Maintain continuous regression checks in automated CI pipeline",
                    "Keep memory limits enforced on all agent containers to prevent OOM issues"
                ] if verdict_status == "GO" else ["Investigate failing assertions in container logs"]
            }
        }

        # Write output report
        os.makedirs(os.path.dirname(output_report_path), exist_ok=True)
        with open(output_report_path, "w") as f:
            json.dump(report, f, indent=2)

        print("\n==================================================================")
        print(f"🎯 Benchmark Verdict: [{verdict_status}]")
        print(f"   • Tasks Completed: {tasks_passed}/{total_tasks} ({pass_rate}%)")
        print(f"   • Assertions     : {passed_assertions}/{total_assertions} ({report['summary']['assertion_pass_rate_percent']}%)")
        print(f"   • Total Duration : {total_duration}s")
        print(f"   • SLA Compliant  : {sla_compliant}")
        print(f"   • Security Gate  : {security_passed}")
        print(f"   • Report Saved   : {output_report_path}")
        print("==================================================================")

        return report

def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--network", default=DEFAULT_NETWORK, help="Docker bridge network name")
    common.add_argument("--gateway-url", default=DEFAULT_GATEWAY_URL, help="Target Go Gateway URL")
    common.add_argument("--engine-url", default=DEFAULT_ENGINE_URL, help="Target Rust Engine URL")

    parser = argparse.ArgumentParser(description="Nexus AI Platform - Multi-Container Harness Controller", parents=[common])
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    # Run single task
    p_run = subparsers.add_parser("run", help="Run a single agent in an isolated container", parents=[common])
    p_run.add_argument("--role", default="qa_test_engineer", help="Target agent role")
    p_run.add_argument("--prompt", required=True, help="Task prompt")
    p_run.add_argument("--cpus", type=float, default=1.0, help="CPU quota")
    p_run.add_argument("--memory", default="256m", help="Memory limit")

    # Eval suite
    p_eval = subparsers.add_parser("eval", help="Run full phased E2E suite", parents=[common])
    p_eval.add_argument("--suite", default="/benchmarks/suite.json", help="Path to suite JSON")
    p_eval.add_argument("--output", default="/results/eval_report.json", help="Path to output report")

    args = parser.parse_args()
    controller = HarnessController(
        network_name=args.network,
        gateway_url=args.gateway_url,
        engine_url=args.engine_url
    )

    if args.cmd == "run":
        res = controller.run_agent_task(
            task_name="Ad-Hoc Agent Verification",
            agent_role=args.role,
            prompt=args.prompt,
            cpus=args.cpus,
            memory_limit=args.memory
        )
        print("\nExecution Output:")
        print(res.get("raw_stdout", ""))

    elif args.cmd == "eval":
        controller.run_e2e_benchmark_suite(args.suite, args.output)

if __name__ == "__main__":
    main()
