# Multi-stage build for Go Gateway
FROM golang:1.23-bookworm AS builder
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /nexus-gateway main.go

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /nexus-gateway /app/nexus-gateway
COPY frontend-web /app/frontend-web

ENV PORT=8080
ENV ENGINE_URL=http://nexus-engine:8085
ENV FRONTEND_DIR=/app/frontend-web

EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/nexus-gateway"]
