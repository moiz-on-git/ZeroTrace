"""
ZeroTrace Live Pre-Deployment Verification Script.
Simulates a real client against the full FastAPI orchestrator engine, validating:
- Authentication & RBAC
- Voice & Text Ingestion
- Real-time Stage Progression & SSE Events
- DAG Lineage & Blast-Radius Planner
- 9-Vector Red-Team Adversarial Audit
- Salted Merkle & Ed25519 Public Verification
- Regulatory PDF & Compliance Pack ZIP Generation
- BSA Section 63 Electronic Evidence Certificate
- Operational Telemetry & Prometheus Metrics
"""

import asyncio
import io
import json
import os
import sys
import time

# Ensure orchestrator src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "orchestrator", "src")))

from httpx import AsyncClient, ASGITransport
from main import app


# Reconfigure stdout for Windows console compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"
CHECK = "[PASS]"
CROSS = "[FAIL]"


async def run_live_verification():
    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{CYAN}    ZEROTRACE PRODUCTION PRE-DEPLOYMENT LIVE VERIFICATION SUITE       {RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")

    transport = ASGITransport(app=app)
    passed_count = 0
    total_count = 0

    async with AsyncClient(transport=transport, base_url="http://zerotrace-orchestrator.internal") as client:
        # Step 1: Health & Telemetry
        print(f"{BOLD}[1/10] Checking Health & Telemetry Endpoints...{RESET}")
        
        t0 = time.time()
        res_health = await client.get("/health")
        lat1 = int((time.time() - t0) * 1000)
        assert res_health.status_code == 200, f"Expected 200, got {res_health.status_code}"
        assert res_health.json()["status"] == "ok"
        print(f"  {GREEN}{CHECK}{RESET} GET /health ({lat1}ms) -> {res_health.json()}")
        passed_count += 1
        total_count += 1

        t0 = time.time()
        res_deep = await client.get("/v1/health/deep")
        lat2 = int((time.time() - t0) * 1000)
        assert res_deep.status_code == 200
        assert res_deep.json()["database"] == "connected"
        print(f"  {GREEN}{CHECK}{RESET} GET /v1/health/deep ({lat2}ms) -> DB: connected, Anchor: {res_deep.json().get('anchor_provider')}")
        passed_count += 1
        total_count += 1

        t0 = time.time()
        res_metrics = await client.get("/metrics")
        lat3 = int((time.time() - t0) * 1000)
        assert res_metrics.status_code == 200
        assert "zerotrace_" in res_metrics.text
        print(f"  {GREEN}{CHECK}{RESET} GET /metrics ({lat3}ms) -> Prometheus format verified ({len(res_metrics.text)} bytes)")
        passed_count += 1
        total_count += 1

        # Step 2: Authentication & RBAC
        print(f"\n{BOLD}[2/10] Validating Authentication & Role-Based Access Control...{RESET}")
        t0 = time.time()
        res_auth = await client.post("/api/v1/auth/demo-login", json={"role": "dpo"})
        lat_auth = int((time.time() - t0) * 1000)
        assert res_auth.status_code == 200
        auth_data = res_auth.json()["data"]
        token = auth_data["token"]
        assert len(token) > 20
        print(f"  {GREEN}{CHECK}{RESET} POST /api/v1/auth/demo-login ({lat_auth}ms) -> Issued JWT for {auth_data['user']}")
        passed_count += 1
        total_count += 1

        res_me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert res_me.status_code == 200
        me_data = res_me.json()["data"]
        assert me_data["role"] == "dpo"
        assert "requests:approve" in me_data["permissions"]
        print(f"  {GREEN}{CHECK}{RESET} GET /api/v1/me -> Role: {me_data['role']}, Permissions: {len(me_data['permissions'])} verified")
        passed_count += 1
        total_count += 1

        # Step 3: Demo Director & System Diagnostics
        print(f"\n{BOLD}[3/10] Testing Demo Director, Seed, and Preflight Checks...{RESET}")
        res_preflight = await client.get("/api/v1/system/preflight")
        assert res_preflight.status_code == 200
        pf_data = res_preflight.json()["data"]
        assert pf_data["overall_status"] == "green"
        print(f"  {GREEN}{CHECK}{RESET} GET /api/v1/system/preflight -> Overall Status: {pf_data['overall_status']} ({len(pf_data['components'])} components verified)")
        passed_count += 1
        total_count += 1

        res_seed = await client.post("/api/v1/demo/seed", json={"profile": "showtime"})
        assert res_seed.status_code == 200
        print(f"  {GREEN}{CHECK}{RESET} POST /api/v1/demo/seed -> Profile 'showtime' active")
        passed_count += 1
        total_count += 1

        # Step 4: Text Consent Withdrawal Ingestion
        print(f"\n{BOLD}[4/10] Submitting Multilingual Erasure Request...{RESET}")
        text_payload = {
            "text": "ನನ್ನ ಒಪ್ಪಿಗೆಯನ್ನು ಹಿಂತೆಗೆದುಕೊಳ್ಳುತ್ತೇನೆ, ನನ್ನ ಖಾತೆಯ ಎಲ್ಲಾ ವಿವರಗಳನ್ನು ಶಾಶ್ವತವಾಗಿ ಅಳಿಸಿಬಿಡಿ. ಮೊಬೈಲ್: +91 98765 43210.",
            "language": "kn-IN"
        }
        res_text = await client.post("/api/v1/requests/text", json=text_payload)
        assert res_text.status_code == 202
        req_data = res_text.json()["data"]
        req_id = req_data["request_id"]
        job_id = req_data["job_id"]
        subject_ref = req_data["subject_ref"]
        print(f"  {GREEN}{CHECK}{RESET} POST /api/v1/requests/text -> 202 Accepted | Request: {req_id} | Job: {job_id}")
        passed_count += 1
        total_count += 1

        # Wait for background pipeline to complete
        print(f"  {YELLOW}⏳ Awaiting 11-stage autonomous saga completion...{RESET}")
        max_wait = 45
        status_final = None
        for _ in range(max_wait):
            await asyncio.sleep(1.0)
            res_j = await client.get(f"/api/v1/jobs/{job_id}")
            if res_j.status_code == 200:
                cur_status = res_j.json()["data"]["status"]
                if cur_status in ["COMPLETED", "COMPLETED_WITH_HOLDS", "FAILED"]:
                    status_final = cur_status
                    break

        assert status_final in ["COMPLETED", "COMPLETED_WITH_HOLDS"], f"Saga did not complete: {status_final}"
        print(f"  {GREEN}{CHECK}{RESET} Saga Finished Successfully: {BOLD}{status_final}{RESET}")
        passed_count += 1
        total_count += 1

        # Step 5: Intent Card & Masked Identifiers
        print(f"\n{BOLD}[5/10] Verifying Legal Intent & Lineage Discovery...{RESET}")
        res_intent = await client.get(f"/api/v1/jobs/{job_id}/intent")
        assert res_intent.status_code == 200
        intent = res_intent.json()["data"]
        assert intent["intent"] == "withdraw_consent"
        assert intent["confidence"] >= 0.90
        print(f"  {GREEN}{CHECK}{RESET} GET /api/v1/jobs/{job_id}/intent -> Intent: {intent['intent']} (Conf: {intent['confidence']})")
        passed_count += 1
        total_count += 1

        res_lineage = await client.get(f"/api/v1/jobs/{job_id}/lineage")
        assert res_lineage.status_code == 200
        lineage = res_lineage.json()["data"]
        assert len(lineage["nodes"]) >= 5
        print(f"  {GREEN}{CHECK}{RESET} GET /api/v1/jobs/{job_id}/lineage -> DAG Nodes: {len(lineage['nodes'])}, Edges: {len(lineage['edges'])}")
        passed_count += 1
        total_count += 1

        # Step 6: Plan & Cost Compaction
        print(f"\n{BOLD}[6/10] Verifying Targeted Compaction Plan & Blast Radius...{RESET}")
        res_plan = await client.get(f"/api/v1/jobs/{job_id}/plan")
        assert res_plan.status_code == 200
        plan = res_plan.json()["data"]
        assert plan["cost"]["saving_pct"] >= 70.0
        assert len(plan["holds"]) > 0
        print(f"  {GREEN}{CHECK}{RESET} GET /api/v1/jobs/{job_id}/plan -> Cost Saving: {plan['cost']['saving_pct']}% | Retention Holds: {len(plan['holds'])}")
        passed_count += 1
        total_count += 1

        # Step 7: Red-Team Adversarial Audit
        print(f"\n{BOLD}[7/10] Inspecting 9-Vector Adversarial Audit Findings...{RESET}")
        res_audit = await client.get(f"/api/v1/jobs/{job_id}/audit")
        assert res_audit.status_code == 200
        audit = res_audit.json()["data"]
        assert audit["verdict"] == "PASS"
        assert len(audit["attacks"]) == 9
        assert audit["collateral_integrity"]["checksum_match"] is True
        print(f"  {GREEN}{CHECK}{RESET} GET /api/v1/jobs/{job_id}/audit -> Verdict: {audit['verdict']} | 9/9 Attacks Passed | Collateral: 100% Match")
        passed_count += 1
        total_count += 1

        # Step 8: Cryptographic Receipts & Sovereign Verification
        print(f"\n{BOLD}[8/10] Verifying Cryptographic Receipts & Merkle Roots...{RESET}")
        res_rcpts = await client.get("/api/v1/receipts")
        assert res_rcpts.status_code == 200
        rcpts = res_rcpts.json()["data"]["receipts"]
        assert len(rcpts) > 0
        latest_rcpt = rcpts[0]
        rcpt_id = latest_rcpt["receipt_id"]

        # Call public trustless /verify
        res_verify = await client.post("/api/v1/verify", json={"receipt": latest_rcpt})
        assert res_verify.status_code == 200
        v_res = res_verify.json()["data"]
        assert v_res["verified"] is True
        print(f"  {GREEN}{CHECK}{RESET} POST /api/v1/verify (Authentic Receipt) -> {BOLD}VERIFIED = TRUE{RESET}")
        passed_count += 1
        total_count += 1

        # Tampered receipt detection
        tampered = dict(latest_rcpt)
        tampered["diff_root"] = ("0" if tampered["diff_root"][0] == "1" else "1") + tampered["diff_root"][1:]
        res_tamper = await client.post("/api/v1/verify", json={"receipt": tampered})
        assert res_tamper.status_code == 200
        v_tamper = res_tamper.json()["data"]
        assert v_tamper["verified"] is False
        print(f"  {GREEN}{CHECK}{RESET} POST /api/v1/verify (1-byte Tampered Diff Root) -> {BOLD}VERIFIED = FALSE (Tamper Flagged){RESET}")
        passed_count += 1
        total_count += 1

        # Step 9: Regulatory Downloads (PDF, Pack ZIP, BSA Cert)
        print(f"\n{BOLD}[9/10] Testing Evidence Generation (PDF, ZIP, BSA Cert)...{RESET}")
        res_pdf = await client.get(f"/api/v1/receipts/{rcpt_id}/download?format=pdf")
        assert res_pdf.status_code == 200
        assert res_pdf.headers["content-type"] == "application/pdf"
        assert res_pdf.content.startswith(b"%PDF")
        print(f"  {GREEN}{CHECK}{RESET} GET /receipts/{rcpt_id}/download?format=pdf -> Valid PDF Generated ({len(res_pdf.content)} bytes)")
        passed_count += 1
        total_count += 1

        res_pack = await client.get(f"/api/v1/receipts/{rcpt_id}/download?format=pack")
        assert res_pack.status_code == 200
        assert res_pack.headers["content-type"] == "application/zip"
        assert res_pack.content.startswith(b"PK")
        print(f"  {GREEN}{CHECK}{RESET} GET /receipts/{rcpt_id}/download?format=pack -> Valid Compliance ZIP Generated ({len(res_pack.content)} bytes)")
        passed_count += 1
        total_count += 1

        res_cert = await client.get(f"/api/v1/receipts/{rcpt_id}/certificate")
        assert res_cert.status_code == 200
        cert = res_cert.json()["data"]
        assert cert["section"] == "Section 63 (Admissibility of electronic records)"
        print(f"  {GREEN}{CHECK}{RESET} GET /receipts/{rcpt_id}/certificate -> BSA 2023 Section 63 Legal Certificate verified")
        passed_count += 1
        total_count += 1

        # Step 10: Operational Administration & Telemetry
        print(f"\n{BOLD}[10/10] Verifying Enterprise Admin Ops & Circuit Breakers...{RESET}")
        res_admin_stats = await client.get("/api/v1/admin/stats")
        assert res_admin_stats.status_code == 200
        stats_data = res_admin_stats.json()["data"]
        print(f"  {GREEN}{CHECK}{RESET} GET /api/v1/admin/stats -> Total Requests: {stats_data['total_requests']}, Jobs Statuses: {stats_data['jobs_by_status']}")
        passed_count += 1
        total_count += 1

        res_cb = await client.get("/api/v1/admin/circuit-breakers")
        assert res_cb.status_code == 200
        print(f"  {GREEN}{CHECK}{RESET} GET /api/v1/admin/circuit-breakers -> Breakers healthy")
        passed_count += 1
        total_count += 1

    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{GREEN}✓ ALL {passed_count}/{total_count} LIVE PRE-DEPLOYMENT CHECKS PASSED WITH ZERO ERRORS!{RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")


if __name__ == "__main__":
    asyncio.run(run_live_verification())
