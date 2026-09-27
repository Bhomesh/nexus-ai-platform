FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY target/release/nexus-engine /app/nexus-engine
RUN chmod +x /app/nexus-engine

ENV NEXUS_HOST=0.0.0.0
ENV NEXUS_PORT=8085

EXPOSE 8085

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/nexus-engine"]
