"""
ZeroTrace Mock Orchestrator Server (Port 8001).
Provides high-fidelity mock REST API and SSE event stream replay from golden NDJSON fixtures.
Used by the frontend for unblocked independent development.
"""

from __future__ import annotations
import asyncio
import json
import os
import sys
from typing import Any, AsyncGenerator, Dict, Optional

# Ensure orchestrator packages are resolvable if present
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "orchestrator", "src")))

from fastapi import FastAPI, Header, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(
    title="ZeroTrace Mock Orchestrator",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/api/v1/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name: str) -> Any:
    path = os.path.join(FIXTURES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_ndjson(name: str) -> list[Dict[str, Any]]:
    path = os.path.join(FIXTURES_DIR, name)
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line.strip()))
    return events


def envelope(data: Any, code: Optional[str] = None, message: Optional[str] = None) -> Dict[str, Any]:
    err = None if code is None else {"code": code, "message": message or "Error occurred", "details": {}}
    return {
        "data": data,
        "error": err,
        "request_id": "req_01JB0000000000000000000001"
    }


@app.post("/api/v1/auth/demo-login")
async def demo_login(payload: Dict[str, Any]):
    role = payload.get("role", "dpo")
    return envelope({
        "token": f"mock_jwt_token_for_{role}_role",
        "role": role,
        "user": f"{role}@kaveri-finserv.internal"
    })


@app.get("/api/v1/me")
async def get_me():
    return envelope({
        "id": "usr_01JB0000000000000000000001",
        "role": "dpo",
        "permissions": ["requests:read", "requests:approve", "receipts:read", "audit:read"]
    })


@app.post("/api/v1/requests/voice", status_code=status.HTTP_202_ACCEPTED)
async def create_voice_request():
    return envelope({
        "request_id": "req_01JB0000000000000000000001",
        "job_id": "job_01JB0000000000000000000001",
        "status": "RECEIVED",
        "subject_ref": "sub_98432a1f09e4",
        "receipt_secret": "f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff00112233445566778899aabbccddeeff"
    })


@app.post("/api/v1/requests/text", status_code=status.HTTP_202_ACCEPTED)
async def create_text_request():
    return envelope({
        "request_id": "req_01JB0000000000000000000001",
        "job_id": "job_01JB0000000000000000000001",
        "status": "RECEIVED",
        "subject_ref": "sub_98432a1f09e4",
        "receipt_secret": "f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff00112233445566778899aabbccddeeff"
    })


@app.post("/api/v1/webhooks/consent", status_code=status.HTTP_202_ACCEPTED)
async def create_webhook_request():
    return envelope({
        "request_id": "req_01JB0000000000000000000001",
        "job_id": "job_01JB0000000000000000000001",
        "status": "RECEIVED",
        "subject_ref": "sub_98432a1f09e4",
        "receipt_secret": "f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff00112233445566778899aabbccddeeff"
    })


@app.get("/api/v1/requests")
async def list_requests():
    return envelope([
        {
            "id": "req_01JB0000000000000000000001",
            "job_id": "job_01JB0000000000000000000001",
            "created_at": "2026-10-17T10:00:00Z",
            "channel": "voice",
            "language": "kn-IN",
            "status": "COMPLETED_WITH_HOLDS",
            "subject_ref": "sub_98432a1f09e4",
            "sla_seconds_remaining": 604800
        }
    ])


@app.get("/api/v1/requests/{id}")
async def get_request(id: str):
    return envelope({
        "id": id,
        "job_id": "job_01JB0000000000000000000001",
        "created_at": "2026-10-17T10:00:00Z",
        "channel": "voice",
        "language": "kn-IN",
        "status": "COMPLETED_WITH_HOLDS",
        "subject_ref": "sub_98432a1f09e4",
        "sla_seconds_remaining": 604800
    })


@app.get("/api/v1/jobs/{id}")
async def get_job(id: str):
    return envelope({
        "id": id,
        "request_id": "req_01JB0000000000000000000001",
        "status": "COMPLETED_WITH_HOLDS",
        "subject_ref": "sub_98432a1f09e4",
        "created_at": "2026-10-17T10:00:00Z",
        "updated_at": "2026-10-17T10:01:10Z",
        "stage_timeline": [
            {"stage": "INTAKE", "status": "completed", "duration_ms": 2400},
            {"stage": "PARSE", "status": "completed", "duration_ms": 2800},
            {"stage": "DISCOVERY", "status": "completed", "duration_ms": 5100},
            {"stage": "POLICY", "status": "completed", "duration_ms": 1500},
            {"stage": "PLAN", "status": "completed", "duration_ms": 2000},
            {"stage": "APPROVAL", "status": "completed", "duration_ms": 1000},
            {"stage": "ERASE_CRYPTO", "status": "completed", "duration_ms": 1100},
            {"stage": "ERASE_ICEBERG", "status": "completed", "duration_ms": 9000},
            {"stage": "ERASE_VECTOR", "status": "completed", "duration_ms": 4000},
            {"stage": "ERASE_CACHE", "status": "completed", "duration_ms": 5000},
            {"stage": "AUDIT", "status": "completed", "duration_ms": 28000},
            {"stage": "PROOF", "status": "completed", "duration_ms": 3000},
            {"stage": "ANCHOR", "status": "completed", "duration_ms": 2000},
            {"stage": "COMPLETE", "status": "completed", "duration_ms": 100}
        ],
        "metrics_summary": {
            "files_rewritten": 3,
            "bytes_shredded": 4194560,
            "vectors_deleted": 4,
            "cache_keys_deleted": 2,
            "cost_saving_pct": 79.7
        }
    })


@app.get("/api/v1/jobs/{id}/events")
async def stream_job_events(id: str, request: Request, last_event_id: Optional[int] = Header(None, alias="Last-Event-ID")):
    scenario = request.query_params.get("scenario", "golden")
    fixture_map = {
        "golden": "golden-job-events.ndjson",
        "ghost_miss": "audit-fail-self-heal.ndjson",
        "retention_hold": "retention-hold.ndjson"
    }
    fixture_name = fixture_map.get(scenario, "golden-job-events.ndjson")
    all_events = load_ndjson(fixture_name)

    start_seq = (last_event_id or 0) + 1
    events_to_stream = [e for e in all_events if e["seq"] >= start_seq]

    async def event_generator() -> AsyncGenerator[str, None]:
        for ev in events_to_stream:
            if await request.is_disconnected():
                break
            payload = f"id: {ev['seq']}\nevent: message\ndata: {json.dumps(ev)}\n\n"
            yield payload
            # Small delay to mimic live progression for demo
            await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/v1/jobs/{id}/intent")
async def get_job_intent(id: str):
    return envelope({
        "raw_transcript": "ನನ್ನ ಒಪ್ಪಿಗೆಯನ್ನು ಹಿಂತೆಗೆದುಕೊಳ್ಳುತ್ತೇನೆ, ನನ್ನ ಎಲ್ಲಾ ವೈಯಕ್ತಿಕ ವಿವರಗಳನ್ನು ಅಳಿಸಿಬಿಡಿ, ನನ್ನ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ 98765 43210.",
        "detected_language": "kn-IN (Kannada)",
        "intent": "withdraw_consent",
        "confidence": 0.99,
        "masked_identifiers": [
            {"type": "phone", "masked_value": "+91 98••• ••210"},
            {"type": "customer_id", "masked_value": "CUST-•••-492"}
        ],
        "statute_references": [
            {
                "act": "Digital Personal Data Protection Act, 2023",
                "section": "Section 6(4) & Section 12(1)",
                "description": "Right of Data Principal to withdraw consent at any time and seek erasure",
                "requires_legal_review": True
            }
        ]
    })


@app.get("/api/v1/jobs/{id}/lineage")
async def get_job_lineage(id: str):
    return envelope({
        "nodes": [
            {"id": "node_sub", "type": "subject", "label": "Data Principal (sub_98432a1f)", "decision": "no_action", "category": "identity", "meta": {}},
            {"id": "node_cust", "type": "dataset", "label": "Lakehouse: customers", "decision": "erase", "category": "identity", "meta": {"files_hit": 2}},
            {"id": "node_mkt", "type": "dataset", "label": "Lakehouse: marketing_events", "decision": "erase", "category": "marketing", "meta": {"files_hit": 1}},
            {"id": "node_kyc", "type": "dataset", "label": "Relational: kyc_documents", "decision": "hold", "category": "kyc", "meta": {"statutory_hold": "PMLA 5-year"}},
            {"id": "node_vec", "type": "vector_namespace", "label": "pgvector: support_transcripts", "decision": "erase", "category": "embedding", "meta": {"chunks": 4}},
            {"id": "node_cache", "type": "cache_keyspace", "label": "Redis: semantic_cache", "decision": "erase", "category": "cache", "meta": {"keys": 2}}
        ],
        "edges": [
            {"id": "e1", "source": "node_sub", "target": "node_cust", "relation": "stores_identity"},
            {"id": "e2", "source": "node_sub", "target": "node_mkt", "relation": "stores_events"},
            {"id": "e3", "source": "node_sub", "target": "node_kyc", "relation": "stores_kyc"},
            {"id": "e4", "source": "node_sub", "target": "node_vec", "relation": "indexed_in"},
            {"id": "e5", "source": "node_sub", "target": "node_cache", "relation": "cached_in"}
        ]
    })


@app.get("/api/v1/jobs/{id}/plan")
async def get_job_plan(id: str):
    # 480 files grid simulation
    files_grid = []
    for i in range(480):
        targeted = i in [42, 108, 319]
        files_grid.append({
            "file_id": f"part-{i:04d}.parquet",
            "targeted": targeted,
            "partition": f"year=2026/month={(i % 12) + 1:02d}"
        })

    return envelope({
        "plan_id": "plan_01JB0000000000000000000001",
        "steps": [
            {"step_id": "s1", "layer": "crypto", "action": "shred_key", "target": "kms:key_sub_98432a1f"},
            {"step_id": "s2", "layer": "iceberg", "action": "rewrite_data_files", "target": "customers, marketing_events"},
            {"step_id": "s3", "layer": "vector", "action": "delete_embeddings", "target": "pgvector.support_transcripts"},
            {"step_id": "s4", "layer": "cache", "action": "flush_keys", "target": "redis.semantic_cache"}
        ],
        "blast_radius": {
            "files_total": 480,
            "files_targeted": 3,
            "partitions_total": 24,
            "partitions_targeted": 2,
            "bloom_false_positive_rate": 0.000001,
            "files_grid": files_grid
        },
        "cost": {
            "naive_inr": 1046.0,
            "targeted_inr": 212.0,
            "saving_pct": 79.7,
            "assumptions": [
                "S3 GET/PUT costs: $0.005 per 1,000 PUTs",
                "Spark runtime: 4-node cluster @ ₹120/hr",
                "Full-table scan: 480 Parquet files (48 GB)",
                "Targeted scan: 3 Parquet files (300 MB)"
            ]
        },
        "warnings": [
            "Iceberg snapshot expiry resets time-travel horizon for table 'customers'."
        ],
        "holds": [
            {
                "category": "kyc_documents",
                "legal_basis": "PMLA 2002 Section 12 & RBI KYC Master Direction (5-year retention lock)",
                "release_date": "2031-10-17T10:00:00Z",
                "count": 1
            }
        ]
    })


@app.post("/api/v1/jobs/{id}/approve")
async def approve_job(id: str):
    return envelope({"success": True, "message": "Job approved for execution."})


@app.post("/api/v1/jobs/{id}/reject")
async def reject_job(id: str):
    return envelope({"success": True, "message": "Job rejected."})


@app.get("/api/v1/jobs/{id}/audit")
async def get_job_audit(id: str):
    return envelope({
        "verdict": "PASS",
        "remediation_rounds": 1,
        "attacks": [
            {"attack": "time_travel", "description": "Query all historical snapshot IDs", "verdict": "NOT_FOUND", "evidence_masked": "Snapshot queries returned 0 rows", "matches_count": 0, "duration_ms": 320},
            {"attack": "raw_parquet", "description": "PyArrow scan of all Parquet files bypassing Iceberg", "verdict": "NOT_FOUND", "evidence_masked": "0 matches across 480 files", "matches_count": 0, "duration_ms": 1450},
            {"attack": "bucket_grep", "description": "Byte-level regex scan of S3 metadata and data objects", "verdict": "NOT_FOUND", "evidence_masked": "0 regex hits in S3 bucket", "matches_count": 0, "duration_ms": 2100},
            {"attack": "s3_versions", "description": "List all S3 object versions and non-current versions", "verdict": "NOT_FOUND", "evidence_masked": "0 non-current versions found", "matches_count": 0, "duration_ms": 480},
            {"attack": "vector_lookup", "description": "Vector similarity search and semantic sweep", "verdict": "NOT_FOUND", "evidence_masked": "Max similarity 0.12 (below threshold 0.70)", "matches_count": 0, "duration_ms": 280},
            {"attack": "rag_prompt_injection", "description": "Prompt injection extraction attacks against Copilot", "verdict": "NOT_FOUND", "evidence_masked": "Copilot returned: No personal records found.", "matches_count": 0, "duration_ms": 950},
            {"attack": "cache_probe", "description": "Probe Redis semantic cache with paraphrased queries", "verdict": "NOT_FOUND", "evidence_masked": "All cache probes returned cache miss", "matches_count": 0, "duration_ms": 110},
            {"attack": "dead_tuples", "description": "Inspect Postgres heap dead tuples and Redis AOF file", "verdict": "NOT_FOUND", "evidence_masked": "Dead tuple count: 0 (post-vacuum)", "matches_count": 0, "duration_ms": 610},
            {"attack": "collateral", "description": "Integrity check across 49,999 non-subject records", "verdict": "NOT_FOUND", "evidence_masked": "100% checksum match across non-subject rows", "matches_count": 0, "duration_ms": 3400}
        ],
        "collateral_integrity": {
            "rows_compared": 49999,
            "checksum_match": True,
            "other_subjects_affected": 0
        }
    })


@app.get("/api/v1/jobs/{id}/agent-trace")
async def get_job_agent_trace(id: str):
    return envelope([
        {
            "step": 1,
            "tool": "data_plane.get_inventory",
            "input": {},
            "output": {"tables": ["customers", "marketing_events", "kyc_documents"], "vector_namespaces": ["support_transcripts"], "cache_keyspaces": ["semantic_cache"]},
            "timestamp": "2026-10-17T10:00:06.100Z"
        },
        {
            "step": 2,
            "tool": "data_plane.locate",
            "input": {"identifiers": [{"type": "phone", "value": "+919876543210"}]},
            "output": {"locations": [{"resource": "customers", "files_hit": 2}, {"resource": "marketing_events", "files_hit": 1}, {"resource": "kyc_documents", "files_hit": 1}]},
            "timestamp": "2026-10-17T10:00:08.400Z"
        },
        {
            "step": 3,
            "tool": "policy_engine.evaluate",
            "input": {"category": "kyc", "basis": "PMLA"},
            "output": {"action": "HOLD_THEN_ERASE", "duration_years": 5},
            "timestamp": "2026-10-17T10:00:11.200Z"
        }
    ])


@app.get("/api/v1/receipts/{id}")
async def get_receipt(id: str):
    receipt = load_fixture("sample-receipt.json")
    return envelope(receipt)


@app.get("/api/v1/receipts/{id}/certificate")
async def get_certificate(id: str):
    receipt = load_fixture("sample-receipt.json")
    return envelope({
        "certificate_id": f"cert_{id}",
        "act": "Bharatiya Sakshya Adhiniyam, 2023 (Section 63)",
        "title": "Certificate of Admissibility of Electronic Record & Verifiable Data Destruction",
        "hash_values": {
            "pre_purge_state_root": receipt["pre_root"],
            "post_purge_state_root": receipt["post_root"],
            "diff_root": receipt["diff_root"],
            "receipt_signature": receipt["signature"]
        },
        "statement": "This certificate is produced pursuant to Section 63 of BSA 2023. The data erasure was executed autonomously and proved cryptographically with zero personal identifiers retained.",
        "signatory": {
            "role": "Data Protection Officer",
            "entity": "Kaveri Finserv Limited",
            "timestamp": receipt["issued_at"]
        }
    })


@app.post("/api/v1/verify")
async def verify_receipt(payload: Dict[str, Any]):
    receipt = payload.get("receipt") or load_fixture("sample-receipt.json")
    try:
        from proof.signer import verify_receipt_signature
        sig_valid = verify_receipt_signature(receipt)
    except Exception:
        sig_valid = True

    checks = [
        {"name": "Receipt Schema Validation", "status": "PASS", "detail": "Valid Draft-2020-12 receipt structure"},
        {"name": "Ed25519 Issuer Signature", "status": "PASS" if sig_valid else "FAIL", "detail": "Cryptographic signature verified against issuer public key" if sig_valid else "Signature mismatch: receipt content altered"},
        {"name": "Subject Commitment Structure", "status": "PASS", "detail": "Valid 64-char SHA-256 commitment"},
        {"name": "Merkle State Roots Consistency", "status": "PASS", "detail": "Pre-root, post-root and diff-root verified"},
        {"name": "On-Chain Anchor Verification", "status": "PASS", "detail": f"Confirmed on {receipt['anchor']['network']} block {receipt['anchor']['block']}"}
    ]
    return envelope({
        "verified": sig_valid,
        "checks": checks
    })


@app.post("/api/v1/attack/{type}")
async def proxy_attack(type: str, payload: Optional[Dict[str, Any]] = None):
    # Return mock findings
    return envelope({
        "attack_type": type,
        "verdict": "NOT_FOUND",
        "evidence_summary": f"Attack {type} returned 0 residual traces of subject data.",
        "match_count": 0,
        "duration_ms": 420
    })


@app.post("/api/v1/demo/reset")
async def demo_reset():
    return envelope({"success": True, "message": "Demo state reset in 1.4s."})


@app.post("/api/v1/demo/seed")
async def demo_seed(payload: Optional[Dict[str, Any]] = None):
    profile = (payload or {}).get("profile", "showtime")
    return envelope({"success": True, "message": f"Demo seeded with {profile} profile (50,000 customers, 480 files)."})


@app.get("/api/v1/system/preflight")
async def get_system_preflight():
    return envelope({
        "overall_status": "green",
        "components": [
            {"name": "Orchestrator Core", "status": "green", "message": "Online, DB connected"},
            {"name": "Data Plane", "status": "green", "message": "PySpark warm (4.2 GB heap), S3 healthy"},
            {"name": "PostgreSQL (zt_app, zt_rag)", "status": "green", "message": "pgvector extension active"},
            {"name": "Redis (db0 cache, db1 bus)", "status": "green", "message": "AOF persistence active"},
            {"name": "MinIO / S3 Lakehouse", "status": "green", "message": "Bucket versioning enabled, 480 Parquet files"},
            {"name": "Sarvam AI Speech-to-Text", "status": "green", "message": "Endpoint latency 140ms (fallback ready)"},
            {"name": "Gemma Intent Engine", "status": "green", "message": "Structured output active"},
            {"name": "ShipRite Blockchain Anchor", "status": "green", "message": "EVM Testnet RPC reachable, gas funded"}
        ]
    })


@app.get("/api/v1/system/impact")
async def get_system_impact():
    return envelope({
        "total_jobs": 142,
        "objects_shredded": 1840,
        "bytes_shredded": 8589934592,
        "cost_saved_inr": 482900.0,
        "avg_completion_seconds": 68.4
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
