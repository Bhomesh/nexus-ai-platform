# Optimized Agent Worker Container
# Isolated execution environment for specialized subagents
FROM python:3.11-slim-bookworm

# Install minimal essential utilities with no cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    git \
    jq \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Security: Create non-privileged agent user
RUN useradd -u 1000 -m -s /bin/bash agentuser

WORKDIR /workspace
RUN chown -R agentuser:agentuser /workspace

COPY runner.py /app/runner.py
RUN chmod +x /app/runner.py

USER agentuser

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python3", "/app/runner.py"]
