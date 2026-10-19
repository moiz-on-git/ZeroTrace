"""
ZeroTrace Stub Data Plane Server (Port 8002).
Implements the exact Data Plane contract (openapi.dataplane.yaml) with high-fidelity simulated responses.
Used by the orchestrator to test all pipeline workflows, retries, self-healing, and manifests.
"""

from __future__ import annotations
import asyncio
import json
import os
from typing import Any, AsyncGenerator, Dict, List, Optional
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(
    title="ZeroTrace Stub Data Plane",
    version="1.0.0",
    docs_url="/docs"
)

# Simulated state
scenario_state = {
    "ghost_miss": False,
    "audit_round": 1
}

HERO_SUBJECT = {
    "subject_id": "sub_hero_ananya",
    "masked_name": "Ananya S••••",
    "masked_phone": "+91 98••• ••210",
    "masked_email": "ananya.s••••@example.com",
    "customer_id": "CUST-4921-KA",
    "identifiers": [
        {"type": "phone", "value": "+919876543210"},
        {"type": "email", "value": "ananya.sharma@example.com"},
        {"type": "customer_id", "value": "CUST-4921-KA"}
    ]
}

DECOYS = [
    {
        "subject_id": "sub_decoy_ananya_mumbai",
        "masked_name": "Ananya S••••",
        "masked_phone": "+91 91••• ••884",
        "masked_email": "ananya.s••••.mh@example.com",
        "customer_id": "CUST-8842-MH",
        "identifiers": [
            {"type": "phone", "value": "+919123456784"},
            {"type": "customer_id", "value": "CUST-8842-MH"}
        ]
    }
]


def envelope(data: Any, code: Optional[str] = None, message: Optional[str] = None) -> Dict[str, Any]:
    err = None if code is None else {"code": code, "message": message or "Error occurred", "details": {}}
    return {
        "data": data,
        "error": err,
        "request_id": "req_dp_01JB0000000000000000000001"
    }


def verify_key(key: Optional[str]):
    # Allow local development if not strictly enforced, but log if missing
    if key and key != "dev-service-key":
        pass


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/health/deep")
async def health_deep(x_service_key: Optional[str] = Header(None, alias="X-Service-Key")):
    return {
        "status": "ok",
        "spark_warm": True,
        "s3_ok": True,
        "pg_ok": True,
        "redis_ok": True,
        "versions": {
            "spark": "3.5.1",
            "iceberg": "1.5.0",
            "pgvector": "0.7.0",
            "redis": "7.2.4"
        }
    }


@app.get("/v1/inventory")
async def get_inventory(x_service_key: Optional[str] = Header(None, alias="X-Service-Key")):
    verify_key(x_service_key)
    return envelope({
        "tables": [
            {
                "name": "customers",
                "layer": "iceberg",
                "format": "parquet_v2",
                "tags": ["identity", "contact"],
                "pii_columns": ["name", "phone", "email", "address", "pan"],
                "total_files": 180
            },
            {
                "name": "loan_applications",
                "layer": "iceberg",
                "format": "parquet_v2",
                "tags": ["financial"],
                "pii_columns": ["customer_id", "phone", "bank_account"],
                "total_files": 120
            },
            {
                "name": "marketing_events",
                "layer": "iceberg",
                "format": "parquet_v2",
                "tags": ["marketing", "behavioural"],
                "pii_columns": ["customer_id", "phone", "ad_id"],
                "total_files": 100
            },
            {
                "name": "kyc_documents",
                "layer": "relational",
                "tags": ["kyc"],
                "pii_columns": ["customer_id", "aadhaar_vault_ref", "passport_no"],
                "total_files": 0
            }
        ],
        "vector_namespaces": [
            {
                "namespace": "support_transcripts",
                "model": "sentence-transformers/all-MiniLM-L6-v2",
                "dimension": 384,
                "total_chunks": 42000
            }
        ],
        "cache_keyspaces": [
            {
                "keyspace": "semantic_cache",
                "backend": "redis_db0",
                "total_keys": 8500
            }
        ]
    })


@app.post("/v1/locate")
async def locate_identifiers(payload: Dict[str, Any], x_service_key: Optional[str] = Header(None, alias="X-Service-Key")):
    verify_key(x_service_key)
    return envelope([
        {
            "location_id": "loc_iceberg_customers",
            "layer": "iceberg",
            "resource": "customers",
            "match_basis": "phone",
            "estimated_rows": 1,
            "data_category": "identity",
            "pii_columns": ["name", "phone", "email"],
            "files_hit": 2,
            "files_total": 180
        },
        {
            "location_id": "loc_iceberg_mkt",
            "layer": "iceberg",
            "resource": "marketing_events",
            "match_basis": "customer_id",
            "estimated_rows": 14,
            "data_category": "marketing",
            "pii_columns": ["customer_id", "phone"],
            "files_hit": 1,
            "files_total": 100
        },
        {
            "location_id": "loc_relational_kyc",
            "layer": "relational",
            "resource": "kyc_documents",
            "match_basis": "customer_id",
            "estimated_rows": 1,
            "data_category": "kyc",
            "pii_columns": ["customer_id", "pan", "aadhaar_vault_ref"],
            "files_hit": 0,
            "files_total": 0
        },
        {
            "location_id": "loc_vector_support",
            "layer": "vector",
            "resource": "support_transcripts",
            "match_basis": "metadata_fk",
            "estimated_rows": 4,
            "data_category": "embedding",
            "pii_columns": ["chunk_text"],
            "files_hit": 0,
            "files_total": 0
        },
        {
            "location_id": "loc_cache_semantic",
            "layer": "cache",
            "resource": "semantic_cache",
            "match_basis": "tag",
            "estimated_rows": 2,
            "data_category": "cache",
            "pii_columns": ["cached_response"],
            "files_hit": 0,
            "files_total": 0
        }
    ])


@app.post("/v1/erasure/plan")
async def create_erasure_plan(payload: Dict[str, Any], x_service_key: Optional[str] = Header(None, alias="X-Service-Key")):
    verify_key(x_service_key)
    job_id = payload.get("job_id", "job_01JB0000000000000000000001")
    return envelope({
        "plan_id": f"plan_{job_id}",
        "steps": [
            {
                "step_id": "step_crypto",
                "layer": "crypto",
                "action": "destroy_subject_data_key",
                "target": "kms:key_sub_hero",
                "est_rows": 0,
                "est_files": 0,
                "est_bytes": 256,
                "est_cost_inr": 0.5,
                "order": 1,
                "parallel_group": "speed1"
            },
            {
                "step_id": "step_lake_rewrite",
                "layer": "iceberg",
                "action": "rewrite_targeted_parquet_and_expire_snapshots",
                "target": "customers, marketing_events",
                "est_rows": 15,
                "est_files": 3,
                "est_bytes": 4194304,
                "est_cost_inr": 212.0,
                "order": 2,
                "parallel_group": "speed2_parallel"
            },
            {
                "step_id": "step_vector_purge",
                "layer": "vector",
                "action": "delete_embeddings_and_vacuum",
                "target": "pgvector:support_transcripts",
                "est_rows": 4,
                "est_files": 0,
                "est_bytes": 65536,
                "est_cost_inr": 15.0,
                "order": 2,
                "parallel_group": "speed2_parallel"
            },
            {
                "step_id": "step_cache_flush",
                "layer": "cache",
                "action": "flush_keys_and_aof_rewrite",
                "target": "redis:semantic_cache",
                "est_rows": 2,
                "est_files": 0,
                "est_bytes": 8192,
                "est_cost_inr": 5.0,
                "order": 2,
                "parallel_group": "speed2_parallel"
            }
        ],
        "blast_radius": {
            "files_total": 480,
            "files_targeted": 3,
            "partitions_total": 24,
            "partitions_targeted": 2,
            "bloom_false_positive_rate": 0.000001
        },
        "cost": {
            "naive_inr": 1046.0,
            "targeted_inr": 212.0,
            "saving_pct": 79.7,
            "assumptions": [
                "Targeted Bloom scan covers only 3 affected data files",
                "Full scan requires rewriting 480 files across 24 partitions"
            ]
        },
        "warnings": [
            "Snapshot expiry will collapse historical time-travel branches for targeted tables."
        ]
    })


@app.post("/v1/erasure/execute", status_code=status.HTTP_202_ACCEPTED)
async def execute_erasure(payload: Dict[str, Any], x_service_key: Optional[str] = Header(None, alias="X-Service-Key")):
    verify_key(x_service_key)
    job_id = payload.get("job_id", "job_01JB0000000000000000000001")
    return envelope({
        "job_id": job_id,
        "status": "EXECUTING",
        "message": "Erasure saga initiated across Lake, Vector, and Cache."
    })


@app.get("/v1/jobs/{job_id}")
async def get_dp_job(job_id: str, x_service_key: Optional[str] = Header(None, alias="X-Service-Key")):
    verify_key(x_service_key)
    return envelope({
        "job_id": job_id,
        "status": "COMPLETED",
        "progress_pct": 100,
        "metrics": {
            "files_rewritten": 3,
            "bytes_shredded": 4194560,
            "snapshots_expired": 4,
            "orphan_files_removed": 3,
            "object_versions_deleted": 6,
            "vectors_deleted": 4,
            "cache_keys_deleted": 2
        }
    })


@app.post("/v1/erasure/remediate")
async def remediate_residuals(payload: Dict[str, Any], x_service_key: Optional[str] = Header(None, alias="X-Service-Key")):
    verify_key(x_service_key)
    # Mark self-healing completed
    scenario_state["ghost_miss"] = False
    scenario_state["audit_round"] = 2
    return envelope({
        "success": True,
        "remediation_round": 1,
        "remediated_locations": payload.get("residual_locations", []),
        "vectors_purged": 1
    })


@app.post("/v1/audit/run")
async def run_audit(payload: Dict[str, Any], x_service_key: Optional[str] = Header(None, alias="X-Service-Key")):
    verify_key(x_service_key)
    # Check if ghost_miss demo flag is enabled
    if scenario_state.get("ghost_miss") and scenario_state.get("audit_round") == 1:
        # Simulate ghost embedding finding!
        findings = [
            {"attack": "time_travel", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 320},
            {"attack": "raw_parquet", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 1450},
            {"attack": "bucket_grep", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 2100},
            {"attack": "s3_versions", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 480},
            {
                "attack": "vector_lookup",
                "verdict": "FOUND",
                "matches_count": 1,
                "evidence_masked": "Unlinked transcript chunk contains +91 98••• ••210",
                "duration_ms": 310
            },
            {"attack": "rag_prompt_injection", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 950},
            {"attack": "cache_probe", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 110},
            {"attack": "dead_tuples", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 610},
            {"attack": "collateral", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 3400}
        ]
        return envelope({
            "verdict": "FAIL",
            "findings": findings,
            "collateral_integrity": {
                "rows_compared": 49999,
                "checksum_match": True,
                "other_subjects_affected": 0
            },
            "residual_locations": [
                {
                    "layer": "vector",
                    "resource": "support_transcripts",
                    "location_id": "chunk_trans_9921",
                    "reason": "Planted ghost embedding detected during semantic sweep"
                }
            ]
        })

    # Clean pass
    return envelope({
        "verdict": "PASS",
        "findings": [
            {"attack": "time_travel", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 320},
            {"attack": "raw_parquet", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 1450},
            {"attack": "bucket_grep", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 2100},
            {"attack": "s3_versions", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 480},
            {"attack": "vector_lookup", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 280},
            {"attack": "rag_prompt_injection", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 950},
            {"attack": "cache_probe", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 110},
            {"attack": "dead_tuples", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 610},
            {"attack": "collateral", "verdict": "NOT_FOUND", "matches_count": 0, "duration_ms": 3400}
        ],
        "collateral_integrity": {
            "rows_compared": 49999,
            "checksum_match": True,
            "other_subjects_affected": 0
        },
        "residual_locations": []
    })


@app.post("/v1/state/manifest")
async def get_state_manifest(payload: Dict[str, Any], x_service_key: Optional[str] = Header(None, alias="X-Service-Key")):
    verify_key(x_service_key)
    label = payload.get("label", "pre")
    if label == "pre":
        items = [
            {"layer": "iceberg", "object_id": "iceberg:customers:part-0001.parquet", "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "in_scope": True, "held": False},
            {"layer": "iceberg", "object_id": "iceberg:marketing:part-0012.parquet", "content_hash": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb", "in_scope": True, "held": False},
            {"layer": "vector", "object_id": "vector:support_tickets:emb_001", "content_hash": "4e07408562bedb8b60ce05c1decfe3ad16b72230967de01f640b7e4729b49fce", "in_scope": True, "held": False},
            {"layer": "cache", "object_id": "cache:semantic:q_loan_status", "content_hash": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a", "in_scope": True, "held": False},
            {"layer": "relational", "object_id": "relational:kyc_documents:row_9942", "content_hash": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d", "in_scope": True, "held": True}
        ]
    else:
        items = [
            {"layer": "relational", "object_id": "relational:kyc_documents:row_9942", "content_hash": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d", "in_scope": True, "held": True}
        ]
    return envelope(items)


@app.post("/v1/attack/{type}")
async def run_single_attack(type: str, payload: Optional[Dict[str, Any]] = None, x_service_key: Optional[str] = Header(None, alias="X-Service-Key")):
    verify_key(x_service_key)
    return envelope({
        "attack_type": type,
        "verdict": "NOT_FOUND",
        "evidence_summary": f"Attack {type} returned 0 residual matches.",
        "match_count": 0,
        "duration_ms": 350
    })


@app.post("/v1/demo/seed")
async def demo_seed(payload: Optional[Dict[str, Any]] = None):
    return envelope({"success": True, "message": "Seeded 50,000 customers, 480 Parquet files."})


@app.post("/v1/demo/reset")
async def demo_reset():
    scenario_state["ghost_miss"] = False
    scenario_state["audit_round"] = 1
    return envelope({"success": True, "message": "Reset to baseline state."})


@app.post("/v1/demo/naive-delete")
async def naive_delete(payload: Optional[Dict[str, Any]] = None):
    return envelope({
        "success": True,
        "message": "Executed naive SQL DELETE (position delete only). Lakehouse Parquet, vectors and cache remain untouched."
    })


@app.get("/v1/demo/subjects")
async def get_demo_subjects():
    return envelope({
        "hero": HERO_SUBJECT,
        "decoys": DECOYS
    })


@app.post("/v1/demo/scenario")
async def set_demo_scenario(payload: Dict[str, Any]):
    ghost_miss = payload.get("ghost_miss", False)
    scenario_state["ghost_miss"] = ghost_miss
    scenario_state["audit_round"] = 1
    return envelope({"scenario": scenario_state})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
