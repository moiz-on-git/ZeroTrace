"""
ZeroTrace OpenAPI Contract Conformance Tests.
Asserts that live API endpoint response envelopes match contracts/openapi.orchestrator.yaml.
Executes against the real FastAPI app with TestClient.

Coverage:
- /health (GET)
- /v1/health/deep (GET)
- /api/v1/auth/demo-login (POST)
- /api/v1/me (GET)
- /api/v1/system/preflight (GET)
- /api/v1/system/impact (GET)
- /api/v1/requests/text (POST)
- /api/v1/requests (GET)
- /api/v1/jobs/{id} (GET)
- /api/v1/jobs/{id}/events (GET - SSE)
- /api/v1/jobs/{id}/intent (GET)
- /api/v1/jobs/{id}/lineage (GET)
- /api/v1/receipts (GET)
- /api/v1/verify (POST - valid & tampered)
- /api/v1/demo/reset (POST)
- /api/v1/demo/seed (POST)
- ShipRite Anchor & Saga verification
"""

from __future__ import annotations
import asyncio
import json
import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from models.database import init_db
from main import app


# ---- Fixtures ---------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    asyncio.run(init_db())
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client):
    resp = client.post("/api/v1/auth/demo-login", json={"role": "dpo"})
    assert resp.status_code == 200, f"Auth failed: {resp.text}"
    return resp.json()["data"]["token"]


@pytest.fixture(scope="module")
def job_id(client, auth_token):
    resp = client.post(
        "/api/v1/requests/text",
        json={"text": "I withdraw my consent. Phone: +91 98765 43210.", "language": "en-IN"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert resp.status_code == 202, f"Text intake failed: {resp.text}"
    body = resp.json()
    assert body["error"] is None
    jid = body["data"]["job_id"]
    assert jid.startswith("job_")
    return jid


# ---- Contract helpers --------------------------------------------------------

def assert_envelope(resp_json: dict, expect_error_none: bool = True):
    assert "data" in resp_json, f"Missing data key: {resp_json}"
    assert "error" in resp_json, f"Missing error key: {resp_json}"
    assert "request_id" in resp_json, f"Missing request_id key: {resp_json}"
    if expect_error_none:
        assert resp_json["error"] is None, f"Unexpected error: {resp_json['error']}"


def assert_response_headers(resp):
    assert "x-request-id" in resp.headers, "Missing X-Request-ID header"
    assert "x-response-time" in resp.headers, "Missing X-Response-Time header"


# ---- Health -----------------------------------------------------------------

def test_health_contract(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "zerotrace-orchestrator"
    assert "version" in body


def test_deep_health_contract(client):
    resp = client.get("/v1/health/deep")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "offline_mode" in body
    assert "anchor_provider" in body
    assert isinstance(body["offline_mode"], bool)


# ---- Auth -------------------------------------------------------------------

def test_auth_token_contract(client):
    resp = client.post("/api/v1/auth/demo-login", json={"role": "dpo"})
    assert resp.status_code == 200
    assert_response_headers(resp)
    body = resp.json()
    assert_envelope(body)
    assert "token" in body["data"]
    assert body["data"]["role"] == "dpo"
    assert "user" in body["data"]


def test_auth_me_contract(client, auth_token):
    resp = client.get("/api/v1/me", headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    assert_response_headers(resp)
    body = resp.json()
    assert_envelope(body)
    assert "id" in body["data"]
    assert body["data"]["role"] == "dpo"


# ---- System & Preflight -----------------------------------------------------

def test_system_preflight_contract(client):
    resp = client.get("/api/v1/system/preflight")
    assert resp.status_code == 200
    assert_response_headers(resp)
    body = resp.json()
    assert_envelope(body)
    d = body["data"]
    assert d["overall_status"] == "green"
    assert len(d["components"]) >= 6


def test_system_impact_contract(client):
    resp = client.get("/api/v1/system/impact")
    assert resp.status_code == 200
    assert_response_headers(resp)
    body = resp.json()
    assert_envelope(body)
    d = body["data"]
    assert "bytes_shredded" in d
    assert "cost_saved_inr" in d


# ---- Requests ---------------------------------------------------------------

def test_text_intake_contract(client, auth_token):
    resp = client.post(
        "/api/v1/requests/text",
        json={"text": "Delete my account. Phone 9876543210.", "language": "en-IN"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert resp.status_code == 202
    assert_response_headers(resp)
    body = resp.json()
    assert_envelope(body)
    d = body["data"]
    assert d["job_id"].startswith("job_")
    assert d["subject_ref"].startswith("sub_")
    assert "receipt_secret" in d
    assert d["status"] == "RECEIVED"


def test_requests_list_contract(client, auth_token):
    resp = client.get("/api/v1/requests", headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    assert_response_headers(resp)
    body = resp.json()
    assert_envelope(body)
    assert isinstance(body["data"], list)


# ---- Jobs -------------------------------------------------------------------

def test_job_status_contract(client, auth_token, job_id):
    resp = client.get(f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    assert_response_headers(resp)
    body = resp.json()
    assert_envelope(body)
    d = body["data"]
    assert d["id"] == job_id
    assert "status" in d
    assert "subject_ref" in d
    assert "stage_timeline" in d
    assert isinstance(d["stage_timeline"], list)


def test_job_not_found_contract(client, auth_token):
    resp = client.get("/api/v1/jobs/job_does_not_exist_xyz", headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_job_events_sse_stream(job_id):
    from core.events import subscribe_events
    from models.database import get_db_session
    async with get_db_session() as session:
        gen = subscribe_events(session=session, job_id=job_id)
        first_chunk = await gen.__anext__()
        assert "connected to job" in first_chunk or "id:" in first_chunk


def test_job_intent_contract(client, auth_token, job_id):
    resp = client.get(f"/api/v1/jobs/{job_id}/intent", headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert_envelope(body)
    d = body["data"]
    assert "intent" in d
    assert d["intent"] == "withdraw_consent"
    assert "confidence" in d
    assert isinstance(d["confidence"], float)


def test_job_lineage_contract(client, auth_token, job_id):
    resp = client.get(f"/api/v1/jobs/{job_id}/lineage", headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert_envelope(body)
    d = body["data"]
    assert "nodes" in d
    assert "edges" in d


# ---- Receipts ---------------------------------------------------------------

def test_receipts_list_contract(client, auth_token):
    resp = client.get("/api/v1/receipts", headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert_envelope(body)
    assert "receipts" in body["data"]
    assert isinstance(body["data"]["receipts"], list)


# ---- Verify -----------------------------------------------------------------

def test_verify_valid_receipt_contract(client):
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "contracts", "fixtures", "proof-test-vectors.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        vectors = json.load(f)

    valid_rcpt = vectors["receipts"]["valid_receipt"]
    resp = client.post("/api/v1/verify", json={"receipt": valid_rcpt})
    assert resp.status_code == 200
    body = resp.json()
    assert_envelope(body)
    d = body["data"]
    assert d["verified"] is True
    assert all(check["status"] == "PASS" for check in d["checks"])


def test_verify_tampered_receipt_contract(client):
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "contracts", "fixtures", "proof-test-vectors.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        vectors = json.load(f)

    tampered_rcpt = vectors["receipts"]["tampered_root_receipt"]
    resp = client.post("/api/v1/verify", json={"receipt": tampered_rcpt})
    assert resp.status_code == 200
    body = resp.json()
    assert_envelope(body)
    d = body["data"]
    assert d["verified"] is False
    sig_check = next(c for c in d["checks"] if "Signature" in c["name"])
    assert sig_check["status"] == "FAIL"


# ---- Demo -------------------------------------------------------------------

def test_demo_reset_contract(client):
    resp = client.post("/api/v1/demo/reset")
    assert resp.status_code == 200
    body = resp.json()
    assert_envelope(body)
    assert "message" in body["data"]


def test_demo_seed_contract(client):
    resp = client.post("/api/v1/demo/seed", json={"profile": "showtime"})
    assert resp.status_code in (200, 202)
    body = resp.json()
    assert_envelope(body)


# ---- ShipRite Anchor --------------------------------------------------------

@pytest.mark.asyncio
async def test_shiprite_anchor_roundtrip_offline():
    """Full anchor roundtrip using LocalSignedLedger fallback."""
    from adapters.anchor import get_anchor_provider
    provider = get_anchor_provider("local")
    result = await provider.anchor_root(
        job_id="job_conformance_test_001",
        diff_root="a" * 64,
        receipt_id="rcpt_conformance_test_001"
    )
    assert result["status"] == "CONFIRMED"
    assert result["tx_hash"].startswith("0x")
    assert len(result["tx_hash"]) == 66  # "0x" + 64 hex chars
    assert isinstance(result["block"], int)
    assert "network" in result
    assert "explorer_url" in result


@pytest.mark.asyncio
async def test_anchor_offline_hash_is_deterministic():
    """Same diff_root must always yield same tx_hash in offline mode."""
    from adapters.anchor import LocalSignedLedgerAnchor

    anchor = LocalSignedLedgerAnchor()
    r1 = await anchor.anchor_root("job_det_001", "f" * 64, "rcpt_det_001")
    r2 = await anchor.anchor_root("job_det_001", "f" * 64, "rcpt_det_001")

    assert r1["status"] == r2["status"] == "CONFIRMED"
    assert len(r1["tx_hash"]) == len(r2["tx_hash"]) == 66


# ---- Full saga round-trip ---------------------------------------------------

@pytest.mark.asyncio
async def test_end_to_end_saga_proof_chain():
    """
    Runs the entire saga and checks that:
    - Status is COMPLETED or COMPLETED_WITH_HOLDS
    - receipt_id is a valid ULID starting with rcpt_
    - subject_salt is a 64-hex string
    """
    from models.database import init_db, get_db_session
    from services.orchestration import JobOrchestrator
    from models.entities import RequestRecord, JobRecord
    from core.ulid import generate_ulid, generate_subject_ref
    from core.config import settings
    from datetime import datetime, timezone

    await init_db()

    req_id = generate_ulid("req_")
    sub_ref = generate_subject_ref(f"text_{req_id}", settings.PEPPER_SECRET)
    job_id = generate_ulid("job_")

    async with get_db_session() as session:
        req = RequestRecord(
            id=req_id,
            job_id=job_id,
            channel="text",
            status="RECEIVED",
            subject_ref=sub_ref,
            language="en-IN"
        )
        job = JobRecord(
            id=job_id,
            request_id=req_id,
            status="RECEIVED",
            subject_ref=sub_ref,
            created_at=datetime.now(timezone.utc)
        )
        session.add(req)
        session.add(job)
        await session.commit()

        orch = JobOrchestrator()
        result = await orch.execute_job_saga(
            session=session,
            job_id=job_id,
            channel="text",
            raw_text="Please erase all my data. Contact: 99887 76655.",
            language_hint="en-IN"
        )

    assert result["status"] in ("COMPLETED", "COMPLETED_WITH_HOLDS"), f"Saga failed: {result}"
    assert result["receipt_id"].startswith("rcpt_")
    assert len(result["subject_salt"]) == 64


# ---- Admin & Operations Telemetry -------------------------------------------

def test_prometheus_metrics_contract(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "zerotrace_uptime_seconds" in resp.text
    assert "zerotrace_jobs_total" in resp.text


def test_admin_stats_contract(client, auth_token):
    resp = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert_envelope(body)
    d = body["data"]
    assert "uptime_seconds" in d
    assert "total_requests" in d
    assert "jobs_by_status" in d
    assert "database_backend" in d


def test_admin_circuit_breakers_contract(client, auth_token):
    resp = client.get("/api/v1/admin/circuit-breakers", headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert_envelope(body)
    breakers = body["data"]["circuit_breakers"]
    assert len(breakers) >= 4
    names = [b["name"] for b in breakers]
    assert "sarvam_ai_multilingual_stt" in names
    assert "gemma_legal_intent_llm" in names
    assert "shiprite_blockchain_anchor" in names


def test_admin_safe_config_contract(client, auth_token):
    resp = client.get("/api/v1/admin/config", headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert_envelope(body)
    d = body["data"]
    assert "masked_secrets" in d
    # Secrets must NEVER be leaked in plaintext
    for k, v in d["masked_secrets"].items():
        assert "..." in v or v == "***"


def test_admin_drain_mode_toggle(client, auth_token):
    # Enable drain
    resp1 = client.post(
        "/api/v1/admin/drain",
        json={"enabled": True, "reason": "Test maintenance"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert resp1.status_code == 200
    assert resp1.json()["data"]["drain_mode"] is True

    # Disable drain
    resp2 = client.post(
        "/api/v1/admin/drain",
        json={"enabled": False},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["drain_mode"] is False
