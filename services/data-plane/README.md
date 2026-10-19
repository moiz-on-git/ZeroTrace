# ZeroTrace — Data Plane Service

> **Owner: Moiz** | Port: `8002` | Stack: Python 3.11 + FastAPI + PySpark 3.5 + Iceberg + pgvector + Redis

The Data Plane is the simulated NBFC data stack **and** the erasure + audit engine for ZeroTrace.

---

## What This Service Does

| Capability | Description |
|---|---|
| **Simulated NBFC stack** | Kaveri Finserv dataset: 50,000 customers across 7 Iceberg tables (~480 Parquet files), pgvector embeddings, Redis semantic cache |
| **Subject Locator Index** | Bloom filters per Parquet file — rewrites only the files that contain the subject |
| **Two-speed erasure** | Speed 1: cryptographic key destroy (instant). Speed 2: physical eradication (lake + vector + cache in parallel) |
| **Correct Iceberg operation order** | DELETE → REWRITE → EXPIRE SNAPSHOTS → REMOVE ORPHANS → PURGE METADATA → PURGE S3 VERSIONS → SCRUB STATS |
| **Adversarial audit** | 9 attack types including time-travel, raw Parquet, bucket grep, vector lookup, RAG prompt injection, cache probe, dead-tuple inspection, collateral integrity |
| **Ghost embedding self-heal** | First pass misses the ghost; audit finds it; remediate fixes it |
| **Retention holds** | KYC/financial data held under PMLA/RBI rules in an encrypted vault |

---

## Quick Start (Docker — recommended)

```bash
# 1. Copy env
cp .env.example .env

# 2. Start the full stack (Postgres + Redis + MinIO + Data Plane)
docker compose -f docker-compose.dataplane.yml up -d --build

# 3. Wait for health
curl http://localhost:8002/health

# 4. Seed the demo dataset
curl -s -X POST http://localhost:8002/v1/demo/seed \
  -H "X-Service-Key: zt-dev-service-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"profile": "small"}'

# 5. Browse the API docs
open http://localhost:8002/docs
```

---

## Quick Start (Local dev without Docker)

**Prerequisites:** Python 3.11+, Java 17+, a running Postgres+Redis+MinIO (or use `docker compose -f docker-compose.dataplane.yml up postgres redis minio minio-setup -d`)

```bash
# Install dependencies
pip install -r requirements.txt

# Download the embedding model once
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2').save('./models/embed')"

# Copy and edit env
cp .env.example .env

# Run the service
python -m uvicorn src.main:app --host 0.0.0.0 --port 8002 --reload
```

---

## Environment Variables

All variables are prefixed `ZT_`. See `.env.example` for the full list and descriptions.

Key variables:

| Variable | Default | Description |
|---|---|---|
| `ZT_SERVICE_KEY` | `changeme-service-key` | Shared secret for X-Service-Key header |
| `ZT_PG_HOST` | `localhost` | Postgres host |
| `ZT_S3_ENDPOINT` | `http://localhost:9000` | MinIO/S3 endpoint |
| `ZT_SPARK_DRIVER_MEMORY` | `4g` | Spark driver memory |
| `ZT_EMBED_MODEL_PATH` | `./models/embed` | Local embedding model path |
| `ZT_DEMO_GHOST_MISS` | `false` | Set `true` to skip semantic sweep on first pass (ghost demo) |
| `ZT_ENABLE_CRYPTO_SHRED` | `false` | Enable cryptographic key-destroy (P1) |

---

## API Reference

Base URL: `http://localhost:8002`  
Auth: All `/v1/*` endpoints require `X-Service-Key` header  
Swagger UI: `http://localhost:8002/docs`

### Key Endpoints

```
GET  /health                    Simple liveness check
GET  /v1/health/deep            Deep health: Spark, S3, Postgres, Redis

GET  /v1/inventory              Schema + PII classification of all tables
POST /v1/locate                 Find subject across all layers

POST /v1/erasure/plan           Build erasure plan (blast radius + cost)
POST /v1/erasure/execute        Execute erasure (async, returns 202)
GET  /v1/jobs/{job_id}          Job status
GET  /v1/jobs/{job_id}/events   SSE event stream (Last-Event-ID replay)
POST /v1/erasure/remediate      Targeted re-erasure of residual locations

POST /v1/audit/run              Full adversarial audit (9 attacks)
POST /v1/attack/{type}          Single attack

POST /v1/state/manifest         Pre/post manifest for Merkle proof

POST /v1/demo/seed              Seed dataset (small | showtime)
POST /v1/demo/reset             Full reset to clean showtime state
POST /v1/demo/naive-delete      Naive DELETE (reproduces the traps for cold open)
GET  /v1/demo/subjects          Hero + decoy descriptors
POST /v1/demo/scenario          Set ghost_miss / auto_approve flags
```

---

## Running Tests

```bash
# All tests
make test

# Unit tests only (no infra required)
make test-unit

# Integration tests (require Redis)
make test-integration
```

---

## Demo CLI

Run the full cycle in the terminal without any frontend:

```bash
python scripts/demo_cli.py --profile small
```

Output shows: seed → naive delete → attacks (FOUND) → plan → execute → audit (PASS) → attacks (NOT_FOUND) → reset.

---

## Architecture Notes

### Spark Session
- One long-lived PySpark session started at boot in a background thread
- `GET /v1/health/deep` reports `spark_warm: true` once ready
- Memory: configurable via `ZT_SPARK_DRIVER_MEMORY` (default 4g)

### Subject Locator Index
- Bloom filters (FPR = 1e-6) per Parquet file stored in Postgres `bloom_filter_index` table
- Candidate files confirmed by actual byte scan — correctness never depends on Bloom alone
- `files_targeted / files_total` ratio shown in plan; typically 2–5% of all files

### Erasure Operation Order (why order matters)
```
1. DELETE rows         → writes positional delete files (MoR)
2. REWRITE data files  → physically removes subject rows from Parquet
3. EXPIRE SNAPSHOTS    → removes old snapshot references
4. REMOVE ORPHANS      ← MUST come AFTER step 3 (this is the trap!)
5. PURGE METADATA      → removes old manifest/metadata versions
6. PURGE S3 VERSIONS   → deletes non-current S3 object versions
7. SCRUB COL STATS     → disables min/max bounds on PII columns
```
Running step 4 before step 3 deletes **zero bytes** — this is demonstrated live in the naive-delete demo mode.

### Ghost Embedding
- Planted at seed time: a transcript chunk mentioning the hero with **no metadata link**
- `ZT_DEMO_GHOST_MISS=true` makes the first physical pass skip the semantic sweep
- The audit catches it → remediate runs → second audit passes → receipt issued

### Memory Budget
| Component | RAM |
|---|---|
| Spark driver | 4 GB (configurable) |
| Python process | ~0.5 GB |
| Embedding model | ~0.5 GB |
| **Total** | **~5 GB** |
Target host: 16 GB shared with orchestrator (~3 GB) and other services.

---

## Makefile Commands

```bash
make up          # Start docker compose stack
make down        # Stop stack
make seed        # Seed small profile
make reset       # Full reset to showtime
make demo        # Run demo CLI
make test        # Run all tests
make lint        # Ruff linter
make typecheck   # mypy
make openapi     # Export openapi.json
make health      # Hit health endpoints
```

---

## Handoff to Platform (Integration)

At **M8** (showtime profile + fast reset working), notify the platform owner:
1. Service runs on `http://localhost:8002`
2. OpenAPI spec: `services/data-plane/openapi.json` (run `make openapi`)
3. Contract: `contracts/openapi.dataplane.yaml`
4. All endpoints are live and match the contract exactly
5. Event stream: `GET /v1/jobs/{job_id}/events` (SSE, supports Last-Event-ID replay)
6. Proposed contract changes: `services/data-plane/CONTRACT_REQUESTS.md`
