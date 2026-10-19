# ZeroTrace Monorepo Integration Checklist & Contract Guide

This document coordinates the parallel development of the Frontend (`apps/web`), Data Plane (`services/data-plane`), and Platform & Orchestrator (`services/orchestrator`) tracks.

---

## 1. Team Ownership Boundaries

| Owner | Directory | Responsibilities |
|---|---|---|
| **Frontend** | `apps/web` | Frontend: Portal, DPO Console, Adversary Console, Public Verifier, Demo Director. |
| **Moiz** | `services/data-plane` | Data Plane: Lakehouse (Iceberg), Vector store (pgvector), Cache (Redis), Seed generator, Attack suite. |
| **Platform** | `services/orchestrator`, `contracts/`, `infra/`, root | Orchestrator, Proof plane, State manifests, Contracts, Platform & Deployment. |

---

## 2. Unblocking Frontend

The frontend can integrate directly with the live, fully tested real orchestrator:

### Primary (Production Backend): Real Orchestrator Engine (Port 8001)
Runs the live FastAPI engine with SQLite/Postgres persistence, real Merkle proof generation, Ed25519 signing, and live SSE event bus:
```bash
uvicorn main:app --app-dir services/orchestrator/src --port 8001 --reload
```
Interactive OpenAPI documentation & testing is available at `http://localhost:8001/docs`.

### Secondary (Isolated Fallback): Mock Orchestrator & Static Fixtures
For offline UI prototyping when running without database dependencies:
```bash
python contracts/mock_orchestrator.py
```
Pre-recorded event fixtures are preserved in `contracts/fixtures/`:
- `contracts/fixtures/golden-job-events.ndjson`: 42-event sequence covering all 11 stages.
- `contracts/fixtures/audit-fail-self-heal.ndjson`: Planted ghost embedding detection, round 1 failure, targeted remediation, and round 2 pass.
- `contracts/fixtures/retention-hold.ndjson`: KYC statutory hold ending in `COMPLETED_WITH_HOLDS`.
- `contracts/fixtures/sample-receipt.json`: Valid cryptographic receipt.
- `contracts/fixtures/proof-test-vectors.json`: Mathematical test vectors for in-browser client-side cryptographic verification (including tamper cases).

---

## 3. Unblocking Moiz (Data Plane)

Moiz builds against `contracts/openapi.dataplane.yaml` (Base path `http://localhost:8002`, header `X-Service-Key: dev-service-key`).
To verify conformance, the platform track has provided:
```bash
# Start stub data plane to inspect expected request/response contracts
python services/orchestrator/src/adapters/stub_dataplane.py
```

### Integration Checkpoints
- [x] **Checkpoint 1**: Contracts frozen in `contracts/` with OpenAPI 3.0 & JSON Schemas.
- [x] **Checkpoint 2**: Orchestrator core & proof plane mathematically verified (48/48 tests passing, 100% green).
- [x] **Checkpoint 3**: End-to-end golden path pipeline verified headlessly (`scripts/e2e_golden_path.py`).
- [x] **Checkpoint 4**: Sub-second cryptographic proof benchmarks validated (`scripts/benchmark_proofs.py`).
- [x] **Checkpoint 5**: Production load test script with p95/p99 SLO validation implemented (`scripts/load_test.py`).
- [x] **Checkpoint 6**: Enterprise operational telemetry & admin suite built (`/metrics`, `/api/v1/admin/stats`, `/admin/drain`).
- [ ] **Checkpoint 7**: Connect the frontend to real orchestrator on port 8001.
- [ ] **Checkpoint 8**: Connect Moiz's PySpark data plane to orchestrator on port 8002.
- [ ] **Checkpoint 9**: Three consecutive full demo runs under 90 seconds without manual intervention.
