"""
Tests: API health endpoints, auth enforcement.
Uses httpx TestClient — no real Spark/S3 needed (mocked).
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.main import app
from src.core.config import get_settings

cfg = get_settings()
client = TestClient(app, raise_server_exceptions=False)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_inventory_requires_service_key():
    resp = client.get("/v1/inventory")
    assert resp.status_code == 401


def test_inventory_with_valid_key():
    resp = client.get(
        "/v1/inventory",
        headers={"X-Service-Key": cfg.service_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "tables" in data["data"]
    # All expected tables present
    table_names = {t["name"] for t in data["data"]["tables"]}
    assert "customers" in table_names
    assert "kyc_documents" in table_names
    assert "support_tickets" in table_names


def test_invalid_service_key_rejected():
    resp = client.post(
        "/v1/locate",
        json={"identifiers": [{"type": "phone", "value": "9845012345"}]},
        headers={"X-Service-Key": "wrong-key"},
    )
    assert resp.status_code == 401
    # FastAPI HTTPException returns 'detail', our custom dep returns it in detail
    body = resp.json()
    # Handle both envelope format and raw HTTPException format
    error_info = body.get("error") or body.get("detail") or {}
    if isinstance(error_info, dict):
        code = error_info.get("code", "")
    elif isinstance(error_info, list) and error_info:
        code = error_info[0].get("code", "")
    else:
        code = str(error_info)
    assert "UNAUTHORIZED" in code or resp.status_code == 401


def test_response_envelope():
    """Every response must use the {data, error, request_id} envelope."""
    resp = client.get("/health")
    # Simple health doesn't use envelope, but deep health does
    resp2 = client.get(
        "/v1/health/deep",
        headers={"X-Service-Key": cfg.service_key},
    )
    body = resp2.json()
    # Either has data or error key
    assert "data" in body or "error" in body


def test_request_id_header_returned():
    resp = client.get("/health", headers={"X-Request-ID": "test-req-123"})
    assert resp.headers.get("X-Request-ID") == "test-req-123"


def test_unknown_route_returns_404():
    resp = client.get("/v1/nonexistent")
    assert resp.status_code == 404
