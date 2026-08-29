# Flaky Test Detector — Deployment Guide

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- A machine with at least 1 GB RAM (the embedding model uses ~200 MB)
- (Optional) A Groq API key for LLM-powered root-cause analysis

---

## Quick Start (single host with Docker Compose)

```bash
# 1. Clone / copy the project
git clone https://github.com/JNamu12/AI_PROJECTS_2026.git
cd "AI_PROJECTS_2026/Project_14_Flaky Test Detector"

# 2. Create your .env from the template
cp backend/.env.example backend/.env
# Edit backend/.env and fill in real values (see below)

# 3. Build and launch
docker compose up -d --build

# 4. Verify it's healthy
curl http://localhost:8000/health
# → {"status":"ok","qdrant":"connected"}
```

The API will be available at **http://localhost:8000**.  
The interactive docs are at **http://localhost:8000/docs**.

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and configure each variable:

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Optional | Groq key for LLM analysis. Leave blank for heuristic mode. |
| `QDRANT_URL` | Optional | Remote Qdrant URL. Leave blank for local file storage. |
| `QDRANT_API_KEY` | Optional | Only needed when `QDRANT_URL` points to a secured Qdrant Cloud instance. |
| `DB_PATH` | Optional | Absolute path for the SQLite DB. Defaults to the Docker volume at `/data/flaky_test_detector.db`. |
| `API_KEY` | **Recommended** | Secret key for the `/ingest` endpoint. Generate with `openssl rand -hex 32`. |
| `ALLOWED_ORIGINS` | Optional | Comma-separated list of frontend origins allowed by CORS. |

---

## Data Persistence

Two Docker named volumes are created automatically:

| Volume | Contents |
|---|---|
| `backend_data` | SQLite database (`flaky_test_detector.db`) |
| `qdrant_local` | Local Qdrant vector store (when `QDRANT_URL` is unset) |

Both survive `docker compose down`. To wipe all data:

```bash
docker compose down -v   # -v removes named volumes
```

---

## Securing the Ingestion Endpoint

When `API_KEY` is set in `.env`, every `POST /api/v1/test-runs/ingest` call must include:

```
X-API-Key: <your_key>
```

**curl example:**
```bash
curl -X POST https://your-host:8000/api/v1/test-runs/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d @payload.json
```

**Python converter tool:**
```bash
python tools/junit_xml_to_ingest.py report.xml \
  --url https://your-host:8000/api/v1/test-runs/ingest \
  --api-key "$API_KEY"
# or set the API_KEY env var and omit --api-key
```

Read-only endpoints (`GET /api/v1/flaky-tests/`) are **not** protected.

---

## Deploying to a VM / VPS

```bash
# Install Docker on Ubuntu 22.04
curl -fsSL https://get.docker.com | sh

# Copy project files to the server (or clone from GitHub)
scp -r . user@your-server:/opt/flaky-detector

# SSH in and start
ssh user@your-server
cd /opt/flaky-detector
cp backend/.env.example backend/.env
nano backend/.env    # fill in real values

docker compose up -d --build
```

To expose the backend over HTTPS, put **nginx** or **Caddy** in front:

```nginx
# /etc/nginx/sites-available/flaky-detector
server {
    listen 443 ssl;
    server_name api.your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/api.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Useful Commands

```bash
# View live logs
docker compose logs -f backend

# Restart after a code change
docker compose up -d --build backend

# Run the health check manually
docker compose exec backend curl -s http://localhost:8000/health

# Open a Python shell inside the container
docker compose exec backend python
```
