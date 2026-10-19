"""
Tests for ShipWright AI code review webhook ingestion.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from main import app

client = TestClient(app)


def test_shipwright_webhook_valid_payload():
    payload = {
        "event": "review_completed",
        "repository": "moiz-on-git/ZeroTrace",
        "pull_request_number": 42,
        "commit_sha": "a1b2c3d4e5f6",
        "verdict": "PASSED",
        "comments_count": 0,
        "summary": "ShipWright AI review: all legal constraints and test vectors verified.",
        "author": "moiz-on-git"
    }

    resp = client.post("/api/v1/webhooks/shipwright", json=payload)
    assert resp.status_code == 202
    data = resp.json()
    assert data["received"] is True
    assert data["verdict"] == "PASSED"
    assert data["audit_event_id"].startswith("audit_sw_")


def test_shipwright_webhook_missing_required_field():
    # Missing required verdict
    payload = {
        "event": "review_completed",
        "repository": "moiz-on-git/ZeroTrace",
        "pull_request_number": 42
    }
    resp = client.post("/api/v1/webhooks/shipwright", json=payload)
    assert resp.status_code == 422


def test_shipwright_webhook_health():
    resp = client.get("/api/v1/webhooks/shipwright/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
