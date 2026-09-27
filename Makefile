.PHONY: all build build-rust build-go start stop status test client clean

all: build

build: build-rust build-go

build-rust:
	@echo "[*] Building Nexus Rust Engine..."
	cd engine-rust && cargo build --release

build-go:
	@echo "[*] Building Nexus Go Gateway..."
	cd gateway-go && go build -o bin/nexus-gateway .

start:
	@./scripts/nexus-control.sh start

stop:
	@./scripts/nexus-control.sh stop

status:
	@./scripts/nexus-control.sh status

client:
	@python3 orchestrator-python/nexus_client.py "Explain how AMD Ryzen 7 5800H and RTX 3060 optimize quantized LLM inference."

clean:
	@echo "[*] Cleaning build artifacts..."
	cd engine-rust && cargo clean
	rm -rf gateway-go/bin data/*.pid data/*.log
