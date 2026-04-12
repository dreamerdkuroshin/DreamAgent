# DreamAgent Deployment Guide

This guide covers deploying the DreamAgent stack in a production environment using Podman (or Docker), Redis/Dragonfly, and PostgreSQL.

## Prerequisites
- Podman (v4+) or Docker Server
- Python 3.11+
- At least 8GB of RAM (for Dragonfly cache & LLM embedding processing)

## Architecture Overview
The system splits into a Hybrid Execution model:
1. **API Server** (FastAPI) handling fast-sync responses and task routing.
2. **Worker Pool** executing heavy loops and multi-agent jobs asynchronously.
3. **Dragonfly/Redis** acting as the Event Bus and Task Queue.

## 1. Environment Setup
Fill out `.env` correctly according to `env_setup.md`. You need a database string `DATABASE_URL` and API keys for AI providers.

## 2. Running with Podman-Compose
Use the bundled compose file to orchestrate the API, Worker, Database, and Dragonfly.

```bash
podman-compose up -d --build
```

### Checking Services
Check if the API and Workers are alive:
```bash
podman logs -f dreamagent-api
podman logs -f dreamagent-worker
```

## 3. Worker Node Details
DreamAgent operates a distributed worker model for heavy agent queries.

If you are running the system outside of docker, launch the worker manually:
```bash
python -m backend.worker --queues tasks:complex,tasks:medium,tasks:simple
```

## 4. Reverse Proxy & SSL (Nginx)
Expose the FastAPI service port (8001) behind Nginx to handle SSL and WebSockets/SSE gracefully. Ensure Nginx does not buffer SSE streams.

```nginx
location /api/v1/stream {
    proxy_pass http://localhost:8001;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
    proxy_cache off;
}
```
