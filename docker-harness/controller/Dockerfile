# Optimized Harness Controller Container
# Manages execution lifecycle, benchmark suites, and agent worker containers
FROM python:3.11-slim-bookworm

# Install Docker CLI and essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    tini \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY controller.py /app/controller.py
RUN chmod +x /app/controller.py

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python3", "/app/controller.py"]
