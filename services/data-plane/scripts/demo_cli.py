#!/usr/bin/env python3
"""
ZeroTrace Data Plane — standalone demo CLI.

Runs the full cycle without any frontend or orchestrator:
  1. Seed (small profile)
  2. Naive delete
  3. Attacks (all should be FOUND — proves resurrection traps)
  4. Plan erasure
  5. Execute erasure
  6. Audit (should be PASS)
  7. Attacks again (all should be NOT_FOUND — proves ZeroTrace works)
  8. Reset

Usage:
  python scripts/demo_cli.py [--profile small|showtime] [--base-url http://localhost:8002]
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import httpx

BASE_URL = "http://localhost:8002"
SERVICE_KEY = "changeme-service-key"
HEADERS = {"X-Service-Key": SERVICE_KEY, "Content-Type": "application/json"}

HERO_IDENTIFIERS = [
    {"type": "customer_id", "value": "KF-CUST-000042"},
    {"type": "phone", "value": "9845012345"},
    {"type": "email", "value": "ananya.krishnamurthy@example.in"},
    {"type": "full_name", "value": "Ananya Krishnamurthy"},
]


def _print(label: str, msg: str, color: str = ""):
    COLORS = {"red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m",
              "blue": "\033[94m", "bold": "\033[1m", "": ""}
    RESET = "\033[0m"
    print(f"{COLORS.get(color, '')}{label:30s}{RESET} {msg}")


def _post(client: httpx.Client, path: str, body: dict) -> dict:
    resp = client.post(f"{BASE_URL}{path}", json=body, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    return resp.json()


def _get(client: httpx.Client, path: str) -> dict:
    resp = client.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def run_demo(profile: str = "small"):
    print("\n" + "═" * 60)
    print("  ZeroTrace Data Plane — Demo CLI")
    print("═" * 60 + "\n")

    with httpx.Client() as client:

        # ── Health check ──────────────────────────────────────────────────────
        _print("[ HEALTH ]", "Checking service health…")
        health = _get(client, "/health")
        _print("", f"Status: {health['status']}", "green")

        # ── Step 1: Seed ──────────────────────────────────────────────────────
        _print("[ SEED ]", f"Seeding {profile} profile…")
        t0 = time.time()
        result = _post(client, "/v1/demo/seed", {"profile": profile})
        elapsed = time.time() - t0
        data = result.get("data", {})
        _print("", f"Done in {elapsed:.1f}s — "
               f"{data.get('tables', {}).get('customers', 0):,} customers, "
               f"{data.get('vectors', {}).get('embedded', 0)} embeddings, "
               f"ghost planted: {data.get('vectors', {}).get('ghost_planted', 0)}",
               "green")

        # ── Step 2: Naive delete (reproduces the trap) ────────────────────────
        _print("[ NAIVE DELETE ]", "Executing naive DELETE (reproduces the traps)…")
        nd = _post(client, "/v1/demo/naive-delete", {
            "job_id": "demo_naive_001",
            "identifiers": HERO_IDENTIFIERS,
        })
        _print("", nd["data"]["trap_explanation"], "yellow")

        # ── Step 3: Attacks — should all be FOUND ─────────────────────────────
        _print("[ ATTACKS — BEFORE ]", "Running attack library (expect FOUND)…")
        audit_body = {
            "job_id": "demo_naive_001",
            "identifiers": HERO_IDENTIFIERS,
            "attacks": ["time_travel", "bucket_grep", "vector_lookup", "cache_probe"],
        }
        audit_result = _post(client, "/v1/audit/run", audit_body)
        findings = audit_result["data"]["findings"]
        for f in findings:
            verdict = f["verdict"]
            color = "red" if verdict == "FOUND" else "green"
            _print(f"  {f['attack_type']}", f"{verdict} — {f['match_count']} match(es)", color)

        found_count = sum(1 for f in findings if f["verdict"] == "FOUND")
        _print("", f"{found_count}/{len(findings)} attacks found data — "
               f"this is the RESURRECTION TRAP", "red")

        # ── Step 4: Plan erasure ──────────────────────────────────────────────
        _print("[ PLAN ]", "Building erasure plan…")
        import ulid
        job_id = f"job_{ulid.new().str.lower()}"
        plan_body = {
            "job_id": job_id,
            "subject_ref": "sub_demo_hero_ananya",
            "identifiers": HERO_IDENTIFIERS,
            "holds": [],
        }
        plan_result = _post(client, "/v1/erasure/plan", plan_body)
        plan = plan_result["data"]
        br = plan["blast_radius"]
        cost = plan["cost"]
        _print("", f"Plan {plan['plan_id']} — "
               f"{br['files_targeted']}/{br['files_total']} files targeted, "
               f"saving {cost['saving_pct']}% vs full rewrite "
               f"(₹{cost['targeted_inr']:.2f} vs ₹{cost['naive_inr']:.2f})",
               "blue")
        if plan["warnings"]:
            for w in plan["warnings"][:2]:
                _print("  WARNING", w, "yellow")
        if plan["holds"]:
            _print("  HOLDS", f"{len(plan['holds'])} category(ies) held (PMLA/RBI)", "yellow")

        # ── Step 5: Execute erasure ────────────────────────────────────────────
        _print("[ EXECUTE ]", "Executing physical erasure (all 3 layers)…")
        exec_body = {"job_id": job_id, "plan_id": plan["plan_id"], "mode": "both"}
        exec_result = _post(client, "/v1/erasure/execute", exec_body)
        _print("", f"Status: {exec_result['data']['status']}", "blue")

        # Poll job status until complete
        for _ in range(60):
            time.sleep(2)
            job_status = _get(client, f"/v1/jobs/{job_id}")
            status = job_status["data"]["status"]
            if status in ("AUDITING", "COMPLETED", "COMPLETED_WITH_HOLDS", "FAILED"):
                break
            sys.stdout.write(f"\r  Status: {status}…")
            sys.stdout.flush()
        print()
        _print("", f"Job status: {status}", "green" if "COMPLETED" in status else "red")

        # ── Step 6: Audit ──────────────────────────────────────────────────────
        _print("[ AUDIT ]", "Running adversarial audit…")
        audit_post = _post(client, "/v1/audit/run", {
            "job_id": job_id,
            "identifiers": HERO_IDENTIFIERS,
        })
        audit_data = audit_post["data"]
        verdict = audit_data["verdict"]
        color = "green" if verdict == "PASS" else "red"
        _print("", f"Overall verdict: {verdict}", color)
        for f in audit_data["findings"]:
            v = f["verdict"]
            fc = "red" if v == "FOUND" else "green"
            _print(f"  {f['attack_type']}", v, fc)
        ci = audit_data["collateral_integrity"]
        _print("  COLLATERAL", (
            f"{ci['rows_compared']:,} rows compared — "
            f"{'OK' if ci['checksum_match'] else 'MISMATCH'}"
        ), "green" if ci["checksum_match"] else "red")

        # ── Step 7: Reset ──────────────────────────────────────────────────────
        _print("[ RESET ]", "Resetting to clean state…")
        t0 = time.time()
        _post(client, "/v1/demo/reset", {})
        elapsed = time.time() - t0
        _print("", f"Reset complete in {elapsed:.1f}s", "green")

    print("\n" + "═" * 60)
    print("  Demo complete.")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZeroTrace Data Plane Demo")
    parser.add_argument("--profile", default="small", choices=["small", "showtime"])
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()
    BASE_URL = args.base_url
    run_demo(args.profile)
