"""
API endpoint and integration contract tests for ZeroTrace Orchestrator.
"""

import json
import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import asyncio
from main import app
from models.database import init_db

# Initialize tables for tests
asyncio.run(init_db())

client = TestClient(app)


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_deep_health_check():
    resp = client.get("/v1/health/deep")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_auth_demo_login():
    resp = client.post("/api/v1/auth/demo-login", json={"role": "dpo"})
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert data["data"]["role"] == "dpo"
    assert "token" in data["data"]


def test_submit_text_request():
    resp = client.post("/api/v1/requests/text", json={
        "text": "I withdraw my consent. Erase all my data. Phone: +91 98765 43210.",
        "language": "en-IN"
    })
    assert resp.status_code == 202
    data = resp.json()
    assert "data" in data
    assert "request_id" in data["data"]
    assert "job_id" in data["data"]
    assert "receipt_secret" in data["data"]


def test_public_verify_endpoint_with_valid_and_tampered_receipts():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "contracts", "fixtures", "proof-test-vectors.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        vectors = json.load(f)

    # 1. Valid receipt verification
    valid_rcpt = vectors["receipts"]["valid_receipt"]
    resp1 = client.post("/api/v1/verify", json={"receipt": valid_rcpt})
    assert resp1.status_code == 200
    res1 = resp1.json()["data"]
    assert res1["verified"] is True
    assert all(check["status"] == "PASS" for check in res1["checks"])

    # 2. Tampered diff_root verification (MUST fail!)
    tampered_rcpt = vectors["receipts"]["tampered_root_receipt"]
    resp2 = client.post("/api/v1/verify", json={"receipt": tampered_rcpt})
    assert resp2.status_code == 200
    res2 = resp2.json()["data"]
    assert res2["verified"] is False
    sig_check = next(c for c in res2["checks"] if "Signature" in c["name"])
    assert sig_check["status"] == "FAIL"


def test_preflight_endpoint():
    resp = client.get("/api/v1/system/preflight")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["overall_status"] == "green"
    assert len(data["components"]) >= 6


def test_system_impact_endpoint():
    resp = client.get("/api/v1/system/impact")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "bytes_shredded" in data
    assert "cost_saved_inr" in data
