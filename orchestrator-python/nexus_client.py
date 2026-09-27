#!/usr/bin/env python3
"""
Nexus Orchestrator & Client (Python).
Binds the Antigravity Agent Swarm, AI Optimizer, Go Concurrency Gateway, and Rust Inference Engine.
"""

import sys
import os
import time
import json
import urllib.request
import urllib.error

# Connect to the core AI Optimizer
sys.path.insert(0, "/home/manjaro/.gemini/ai-optimizer/core")
try:
    from token_budgeter import TokenBudgeter
    from cache_manager import CacheManager
    from hierarchical_memory import HierarchicalMemoryManager
    from output_compactor import OutputCompactor
except ImportError:
    TokenBudgeter = None

GATEWAY_URL = "http://127.0.0.1:8080"
ENGINE_URL = "http://127.0.0.1:8085"

class NexusAIClient:
    def __init__(self, gateway_url: str = GATEWAY_URL, engine_url: str = ENGINE_URL):
        self.gateway_url = gateway_url
        self.engine_url = engine_url
        self.budgeter = TokenBudgeter() if TokenBudgeter else None
        self.memory = HierarchicalMemoryManager() if HierarchicalMemoryManager else None

    def get_hardware_telemetry(self) -> dict:
        """Fetches live hardware telemetry from Go Concurrency Gateway."""
        try:
            req = urllib.request.Request(f"{self.gateway_url}/api/telemetry")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": f"Gateway unreachable: {e}"}

    def list_mcp_tools(self) -> list:
        """Lists active Model Context Protocol tools from the Go gateway."""
        try:
            req = urllib.request.Request(f"{self.gateway_url}/api/mcp/tools")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return json.loads(resp.read().decode()).get("tools", [])
        except Exception as e:
            return []

    def execute_mcp_tool(self, tool_name: str, args: dict) -> dict:
        """Executes a tool call through the Go worker pool."""
        try:
            payload = json.dumps({"tool": tool_name, "args": args}).encode()
            req = urllib.request.Request(
                f"{self.gateway_url}/api/mcp/execute",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stream_chat_completion(self, user_prompt: str, model: str = "qwen-2.5-coder-7b-q4_k_m"):
        """
        Streams completion tokens directly from the local Rust inference engine (via Go gateway).
        """
        print(f"\n[*] Querying Nexus Engine [{model}]...")
        # Prepare context with Token Budgeter if available
        messages = [{"role": "user", "content": user_prompt}]
        if self.budgeter:
            budgets = self.budgeter.calculate_budgets()
            est_tokens = self.budgeter.estimate_tokens(user_prompt)
            print(f"[*] Token Budget: {est_tokens} tokens allocated (Target: <{budgets['active_query']})")

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "stream": True
        }).encode()

        try:
            req = urllib.request.Request(
                f"{self.gateway_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                for line in resp:
                    line_str = line.decode('utf-8').strip()
                    if line_str.startswith("data:"):
                        data_part = line_str[5:].strip()
                        if data_part == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_part)
                            delta = chunk["choices"][0]["delta"]
                            if "content" in delta and delta["content"]:
                                sys.stdout.write(delta["content"])
                                sys.stdout.flush()
                        except Exception:
                            pass
            print("\n")
        except Exception as e:
            print(f"[-] Inference error: {e}")

def main():
    client = NexusAIClient()
    print("====================================================")
    print("  Nexus AI Platform: Unified System Orchestrator   ")
    print("====================================================")
    
    # Check Gateway & Telemetry
    telem = client.get_hardware_telemetry()
    print("\n[+] Hardware Telemetry (via Go Concurrency Gateway):")
    for k, v in telem.items():
        print(f"    • {k:<20}: {v}")

    # Check MCP Tools
    tools = client.list_mcp_tools()
    print(f"\n[+] Active MCP Protocol Tools ({len(tools)} available):")
    for t in tools:
        print(f"    • {t['name']:<22} [{t['category']}]: {t['description']}")

    # If prompt supplied via arguments, run inference
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        client.stream_chat_completion(query)

if __name__ == "__main__":
    main()
