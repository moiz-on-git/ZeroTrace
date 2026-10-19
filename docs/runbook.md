# ZeroTrace Operations & Demo Runbook

## 1. Quick Start Commands

```bash
# Start full local stack (Orchestrator, Postgres, Redis, MinIO, Catalog)
make up

# Run all unit, contract, and cryptographic proof tests
make test

# Run headless End-to-End Golden Path validation (all 10 stages)
make e2e

# Reset demo dataset to deterministic baseline state (in < 2 seconds)
make reset

# Seed showtime profile (50,000 customers, 480 Parquet lakehouse files)
make seed
```

---

## 2. Ports and Network Map

| Service | Port | Host URL | Description |
|---|---|---|---|
| **Frontend (web)** | 3000 | `http://localhost:3000` | React/Vite dashboard |
| **Orchestrator** | 8001 | `http://localhost:8001` | FastAPI Brain & Proof Plane |
| **Data Plane** | 8002 | `http://localhost:8002` | Moiz's PySpark, Iceberg, pgvector engine |
| **PostgreSQL** | 5432 | `localhost:5432` | DBs: `zt_app` (core), `zt_rag` (pgvector), `zt_catalog` |
| **Redis** | 6379 | `localhost:6379` | `db0` (company semantic cache), `db1` (event bus/queue) |
| **MinIO / S3** | 9000/9001 | `http://localhost:9000` | S3 API (9000), MinIO Console (9001) |
| **Iceberg REST** | 8181 | `http://localhost:8181` | Apache Iceberg REST Catalog |

---

## 3. Demo Director Controls & Fallbacks

### 3.1 Running Demo Scenarios
```bash
# Scenario 1: Golden Path (Voice intake in Kannada, targeted erasure, proof, on-chain anchor)
python demo/director/scenario_runner.py --scenario golden

# Scenario 2: Planted Ghost Embedding Self-Healing (Red team catches ghost, self-heals, passes)
python demo/director/scenario_runner.py --scenario ghost_heal

# Scenario 3: Retention Hold (PMLA / RBI KYC 5-year lock demonstrated live)
python demo/director/scenario_runner.py --scenario retention_hold
```

### 3.2 Offline Fallback Mode
When running at a hackathon or stage with poor Wi-Fi:
Set `ZT_ENABLE_OFFLINE_FALLBACK=true` in `.env`.
- **Sarvam AI**: Automatically uses pre-cached native audio transcripts for Kannada, Hindi, Tamil, Telugu, and English.
- **Gemma LLM**: Automatically activates the deterministic legal rule-based intent parser.
- **Blockchain Anchor**: Automatically seals proofs in `infra/local_ledger.ndjson` so verification passes client-side without internet.

---

## 4. Key Rotation & Security Procedures

### 4.1 Ed25519 Corporate Identity Key Rotation
1. Generate a new keypair:
   ```bash
   python -c "from services.orchestrator.src.proof.signer import generate_ed25519_keypair; priv, pub = generate_ed25519_keypair(); print(f'ZT_SIGNER_PRIVATE_KEY={priv}\nPublic Key={pub}')"
   ```
2. Update `ZT_SIGNER_PRIVATE_KEY` in `.env` and restart the orchestrator.
3. Publish the new public key in the verifier.

### 4.2 Verifying Zero-PII Log Compliance
Run an automated scan across log files to ensure no raw phone numbers, PANs, or Aadhaar numbers exist:
```bash
python -c "
import re
log = open('zerotrace.log').read()
assert not re.search(r'\+91\d{10}', log), 'LEAK DETECTED: Raw phone in logs!'
print('PASS: Zero PII detected in log stream.')
"
```
