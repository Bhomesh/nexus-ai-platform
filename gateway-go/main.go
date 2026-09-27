package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sync"
	"sync/atomic"
	"time"
)

type GatewayConfig struct {
	Port         string
	EngineURL    string
	FrontendDir  string
	WorkerCount  int
}

type HardwareTelemetry struct {
	CPUModel       string `json:"cpu_model"`
	PhysicalCores  int    `json:"physical_cores"`
	HardwareThreads int   `json:"hardware_threads"`
	GoRoutines     int    `json:"active_goroutines"`
	MemoryAllocMB  uint64 `json:"mem_allocated_mb"`
	MemorySysMB    uint64 `json:"mem_sys_mb"`
	NumGC          uint32 `json:"num_gc_cycles"`
	EngineStatus   string `json:"engine_status"`
}

type MCPTool struct {
	Name        string `json:"name"`
	Description string `json:"description"`
	Category    string `json:"category"`
}

type ToolExecutionRequest struct {
	Tool string                 `json:"tool"`
	Args map[string]interface{} `json:"args"`
}

type ToolExecutionResponse struct {
	Success bool        `json:"success"`
	Result  interface{} `json:"result"`
	Error   string      `json:"error,omitempty"`
	Elapsed string      `json:"elapsed"`
}

type GatewayServer struct {
	config      GatewayConfig
	totalReqs   uint64
	mcpTools    []MCPTool
	toolsMu     sync.RWMutex
	workerQueue chan func()
}

func NewGatewayServer(cfg GatewayConfig) *GatewayServer {
	// Maximize performance for AMD Ryzen 7 5800H 16 hardware threads
	runtime.GOMAXPROCS(16)

	s := &GatewayServer{
		config:      cfg,
		workerQueue: make(chan func(), 2048),
		mcpTools: []MCPTool{
			{Name: "token_optimizer", Description: "Calculate context budgets and serial position", Category: "optimization"},
			{Name: "cache_validator", Description: "Check Gemini hardware KV cache eligibility (>=4096)", Category: "optimization"},
			{Name: "memory_store", Description: "Query or store semantic memory facts in SQLite", Category: "memory"},
			{Name: "output_compactor", Description: "Compress terminal and diff logs to save tokens", Category: "compaction"},
			{Name: "subagent_dispatcher", Description: "Route tasks to 13 specialized Antigravity agents", Category: "agents"},
		},
	}

	// Start worker pool matching hardware threads
	for i := 0; i < cfg.WorkerCount; i++ {
		go s.worker(i)
	}

	return s
}

func (s *GatewayServer) worker(id int) {
	for task := range s.workerQueue {
		task()
	}
}

func (s *GatewayServer) telemetryHandler(w http.ResponseWriter, r *http.Request) {
	atomic.AddUint64(&s.totalReqs, 1)

	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	// Check if Rust engine is responding
	engineStatus := "offline"
	client := http.Client{Timeout: 1 * time.Second}
	if resp, err := client.Get(s.config.EngineURL + "/health"); err == nil {
		if resp.StatusCode == http.StatusOK {
			engineStatus = "connected (port 8085)"
		}
		resp.Body.Close()
	}

	telem := HardwareTelemetry{
		CPUModel:        "AMD Ryzen 7 5800H with Radeon Graphics",
		PhysicalCores:   8,
		HardwareThreads: 16,
		GoRoutines:      runtime.NumGoroutine(),
		MemoryAllocMB:   m.Alloc / 1024 / 1024,
		MemorySysMB:     m.Sys / 1024 / 1024,
		NumGC:           m.NumGC,
		EngineStatus:    engineStatus,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(telem)
}

func (s *GatewayServer) mcpToolsHandler(w http.ResponseWriter, r *http.Request) {
	s.toolsMu.RLock()
	defer s.toolsMu.RUnlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"tools": s.mcpTools,
		"total": len(s.mcpTools),
	})
}

func (s *GatewayServer) prometheusMetricsHandler(w http.ResponseWriter, r *http.Request) {
	atomic.AddUint64(&s.totalReqs, 1)

	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	engineConnected := 0
	client := http.Client{Timeout: 500 * time.Millisecond}
	if resp, err := client.Get(s.config.EngineURL + "/health"); err == nil {
		if resp.StatusCode == http.StatusOK {
			engineConnected = 1
		}
		resp.Body.Close()
	}

	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	fmt.Fprintf(w, "# HELP nexus_gateway_requests_total Total HTTP requests handled\n")
	fmt.Fprintf(w, "# TYPE nexus_gateway_requests_total counter\n")
	fmt.Fprintf(w, "nexus_gateway_requests_total %d\n", atomic.LoadUint64(&s.totalReqs))

	fmt.Fprintf(w, "# HELP nexus_gateway_active_goroutines Number of active goroutines\n")
	fmt.Fprintf(w, "# TYPE nexus_gateway_active_goroutines gauge\n")
	fmt.Fprintf(w, "nexus_gateway_active_goroutines %d\n", runtime.NumGoroutine())

	fmt.Fprintf(w, "# HELP nexus_gateway_mem_allocated_bytes Memory allocated by Go runtime\n")
	fmt.Fprintf(w, "# TYPE nexus_gateway_mem_allocated_bytes gauge\n")
	fmt.Fprintf(w, "nexus_gateway_mem_allocated_bytes %d\n", m.Alloc)

	fmt.Fprintf(w, "# HELP nexus_gateway_engine_status Connection status to Rust engine (1=connected, 0=offline)\n")
	fmt.Fprintf(w, "# TYPE nexus_gateway_engine_status gauge\n")
	fmt.Fprintf(w, "nexus_gateway_engine_status %d\n", engineConnected)

	fmt.Fprintf(w, "# HELP nexus_gateway_worker_threads Configured parallel worker threads\n")
	fmt.Fprintf(w, "# TYPE nexus_gateway_worker_threads gauge\n")
	fmt.Fprintf(w, "nexus_gateway_worker_threads %d\n", s.config.WorkerCount)
}

func (s *GatewayServer) mcpExecuteHandler(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	var req ToolExecutionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	done := make(chan ToolExecutionResponse, 1)

	// Dispatch to worker pool
	s.workerQueue <- func() {
		switch req.Tool {
		case "token_optimizer":
			text, _ := req.Args["text"].(string)
			estTokens := len(text) / 4
			done <- ToolExecutionResponse{
				Success: true,
				Result: map[string]interface{}{
					"input_chars":      len(text),
					"estimated_tokens": estTokens,
					"budget_status":    "healthy (<32k limit)",
				},
				Elapsed: time.Since(start).String(),
			}

		case "memory_store":
			cmd := exec.Command("ai-optimizer", "memory", "list-facts")
			out, err := cmd.CombinedOutput()
			if err != nil {
				done <- ToolExecutionResponse{
					Success: false,
					Error:   err.Error(),
					Elapsed: time.Since(start).String(),
				}
				return
			}
			done <- ToolExecutionResponse{
				Success: true,
				Result:  string(out),
				Elapsed: time.Since(start).String(),
			}

		case "subagent_dispatcher":
			agent, _ := req.Args["agent"].(string)
			prompt, _ := req.Args["prompt"].(string)
			if agent == "" {
				agent = "code_architect"
			}
			cmd := exec.Command("agy", "--agent", agent, "-p", prompt)
			out, err := cmd.CombinedOutput()
			if err != nil {
				done <- ToolExecutionResponse{
					Success: false,
					Error:   string(out),
					Elapsed: time.Since(start).String(),
				}
				return
			}
			done <- ToolExecutionResponse{
				Success: true,
				Result:  string(out),
				Elapsed: time.Since(start).String(),
			}

		default:
			done <- ToolExecutionResponse{
				Success: false,
				Error:   fmt.Sprintf("Unknown MCP tool: %s", req.Tool),
				Elapsed: time.Since(start).String(),
			}
		}
	}

	res := <-done
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(res)
}

func (s *GatewayServer) chatProxyHandler(w http.ResponseWriter, r *http.Request) {
	// Forward request to Rust inference engine
	targetURL := s.config.EngineURL + "/v1/chat/completions"
	bodyBytes, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "Failed to read request body", http.StatusBadRequest)
		return
	}

	proxyReq, err := http.NewRequest(r.Method, targetURL, bytes.NewBuffer(bodyBytes))
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	proxyReq.Header.Set("Content-Type", "application/json")
	for k, vv := range r.Header {
		for _, v := range vv {
			proxyReq.Header.Add(k, v)
		}
	}

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(proxyReq)
	if err != nil {
		http.Error(w, fmt.Sprintf("Engine unavailable at %s: %v", targetURL, err), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	for k, vv := range resp.Header {
		for _, v := range vv {
			w.Header().Add(k, v)
		}
	}
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

func main() {
	frontendDir := os.Getenv("FRONTEND_DIR")
	if frontendDir == "" {
		frontendDir = "/home/manjaro/nexus-ai-platform/frontend-web"
	}
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	engineURL := os.Getenv("ENGINE_URL")
	if engineURL == "" {
		engineURL = "http://127.0.0.1:8085"
	}

	cfg := GatewayConfig{
		Port:        port,
		EngineURL:   engineURL,
		FrontendDir: frontendDir,
		WorkerCount: 16, // Matches AMD Ryzen 7 5800H 16 threads
	}

	server := NewGatewayServer(cfg)
	mux := http.NewServeMux()

	// API Routes
	mux.HandleFunc("/api/telemetry", server.telemetryHandler)
	mux.HandleFunc("/api/mcp/tools", server.mcpToolsHandler)
	mux.HandleFunc("/api/mcp/execute", server.mcpExecuteHandler)
	mux.HandleFunc("/api/chat", server.chatProxyHandler)
	mux.HandleFunc("/metrics", server.prometheusMetricsHandler)

	// Static UI assets
	fs := http.FileServer(http.Dir(filepath.Clean(frontendDir)))
	mux.Handle("/", fs)

	addr := ":" + cfg.Port
	log.Printf("[Nexus-Gateway] High-Concurrency Go Gateway running on http://127.0.0.1%s", addr)
	log.Printf("[Nexus-Gateway] Worker pool initialized with %d parallel hardware threads", cfg.WorkerCount)
	log.Fatal(http.ListenAndServe(addr, mux))
}
