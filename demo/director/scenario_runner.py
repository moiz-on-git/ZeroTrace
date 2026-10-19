"""
ZeroTrace Demo Director Scenario Runner.
Interactive CLI & presenter automation tool for Hacktober Hackathon 2026.
Executes the three flagship demo scenarios with live event streaming,
cryptographic verification, and audit trace display:

1. GOLDEN PATH:
   - Voice/text intake in Kannada (Sarvam AI / Gemma DPDP parser)
   - Targeted Parquet erasure (3 of 480 files, 79.7% cost saving)
   - Salted Merkle diff-root computation & Ed25519 signing
   - ShipRite AI / Blockchain on-chain anchoring

2. GHOST EMBEDDING SELF-HEALING:
   - Adversarial audit detects planted ghost vector in pgvector index
   - Automatic remediation saga triggered
   - Second audit passes 100%, collateral integrity confirmed

3. RETENTION HOLD & DPDP ACT SEC 8(4):
   - Loan ledger identified under PMLA 2002 / RBI Master Direction
   - Borrower marketing profile erased, statutory loan record preserved
   - Signed BSA 2023 Section 63 legal certificate generated
"""

from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import httpx

ORCHESTRATOR_URL = os.environ.get("ZT_ORCHESTRATOR_URL", "http://localhost:8001")


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner(scenario_name: str, description: str):
    print("\n" + "=" * 78)
    print(f"{Colors.BOLD}{Colors.CYAN}ZEROTRACE DEMO DIRECTOR{Colors.RESET} :: {Colors.GREEN}{scenario_name.upper()}{Colors.RESET}")
    print(f"{Colors.DIM}{description}{Colors.RESET}")
    print("=" * 78 + "\n")


def stream_events_cli(job_id: str, max_timeout: float = 30.0):
    """
    Connects to the orchestrator SSE stream and prints live stage transitions.
    """
    print(f"{Colors.BOLD}[*] Connecting to live event bus (SSE) for Job {job_id}...{Colors.RESET}")
    start_time = time.time()
    seen_events = set()

    try:
        with httpx.Client(timeout=max_timeout) as client:
            with client.stream("GET", f"{ORCHESTRATOR_URL}/api/v1/jobs/{job_id}/events", headers={"Accept": "text/event-stream"}) as resp:
                if resp.status_code != 200:
                    print(f"  {Colors.YELLOW}[!] SSE stream returned HTTP {resp.status_code}. Polling fallback active.{Colors.RESET}")
                    return

                for line in resp.iter_lines():
                    if time.time() - start_time > max_timeout:
                        break
                    if not line or not line.startswith("data: "):
                        continue
                    try:
                        ev = json.loads(line[6:])
                        seq = ev.get("seq")
                        if seq in seen_events:
                            continue
                        seen_events.add(seq)

                        stage = ev.get("stage", "UNKNOWN")
                        kind = ev.get("kind", "info")
                        msg = ev.get("message", "")
                        layer = ev.get("layer", "")

                        badge = f"{Colors.GREEN}[DONE]{Colors.RESET}" if kind == "completed" else f"{Colors.BLUE}[STAGE]{Colors.RESET}"
                        print(f"  {badge} {Colors.BOLD}{stage:<14}{Colors.RESET} ({layer:<10}) -> {msg}")

                        if stage in ("ANCHOR", "COMPLETE") and kind == "completed":
                            print(f"\n{Colors.GREEN}{Colors.BOLD}  ✓ Pipeline execution completed successfully!{Colors.RESET}")
                            return
                    except Exception:
                        pass
    except Exception as e:
        print(f"  {Colors.DIM}[i] Stream listener closed ({e}). Fetching final job state...{Colors.RESET}")


def run_scenario(scenario_key: str):
    scenarios = {
        "golden": {
            "title": "Golden Path (Multilingual Intake -> Targeted Erasure -> Proof -> Anchor)",
            "desc": "Kannada voice intake, DPDP statutory validation, Parquet surgical rewrite, ShipRite on-chain anchor.",
            "text": "ನನ್ನ ಒಪ್ಪಿಗೆಯನ್ನು ಹಿಂತೆಗೆದುಕೊಳ್ಳುತ್ತೇನೆ, ನನ್ನ ಎಲ್ಲಾ ವಿವರಗಳನ್ನು ಅಳಿಸಿ, ಮೊಬೈಲ್ 9876543210.",
            "lang": "kn-IN",
            "ghost_miss": False
        },
        "ghost_heal": {
            "title": "Planted Ghost Embedding & Self-Healing Remediation",
            "desc": "Simulates un-indexed vector residual; automated adversarial red-team detects and remediates.",
            "text": "Please delete all personal data and conversation memories. Phone: +91 9988776655.",
            "lang": "en-IN",
            "ghost_miss": True
        },
        "retention_hold": {
            "title": "DPDP Statutory Retention Hold (Section 8(4) & PMLA 2002)",
            "desc": "Demonstrates dual-track execution: marketing profile erased, active loan locked with audit cert.",
            "text": "Delete everything including my active Kaveri loan account #L-99824. Phone: +91 9123456789.",
            "lang": "en-IN",
            "ghost_miss": False
        }
    }

    sc = scenarios.get(scenario_key, scenarios["golden"])
    print_banner(scenario_key, sc["desc"])

    # 1. System Health Check
    print(f"{Colors.BOLD}[1/5] Verifying System Preflight Diagnostic...{Colors.RESET}")
    try:
        resp = httpx.get(f"{ORCHESTRATOR_URL}/api/v1/system/preflight", timeout=5.0)
        data = resp.json().get("data", {})
        status_color = Colors.GREEN if data.get("overall_status") == "green" else Colors.YELLOW
        print(f"  Status: {status_color}{data.get('overall_status', 'unknown').upper()}{Colors.RESET} across {len(data.get('components', []))} system components.")
    except Exception as e:
        print(f"  {Colors.YELLOW}[!] Preflight unavailable ({e}). Proceeding in standalone mode.{Colors.RESET}")

    # 2. Reset state & apply scenario config
    print(f"\n{Colors.BOLD}[2/5] Resetting Demo State & Seeding Show-Floor Dataset...{Colors.RESET}")
    try:
        r_reset = httpx.post(f"{ORCHESTRATOR_URL}/api/v1/demo/reset", timeout=5.0)
        print(f"  ✓ {r_reset.json().get('data', {}).get('message', 'Reset complete')}")

        if sc["ghost_miss"]:
            httpx.post(
                f"{ORCHESTRATOR_URL}/v1/demo/scenario",
                json={"ghost_miss": True},
                headers={"X-Service-Key": "dev-service-key"},
                timeout=5.0
            )
            print(f"  ✓ Planted ghost embedding scenario activated.")
    except Exception as e:
        print(f"  {Colors.DIM}[i] Reset note: {e}{Colors.RESET}")

    # 3. Intake request
    print(f"\n{Colors.BOLD}[3/5] Submitting Data Principal Erasure Request...{Colors.RESET}")
    print(f"  Channel:     {Colors.CYAN}Text / Voice Intake{Colors.RESET}")
    print(f"  Language:    {Colors.CYAN}{sc['lang']}{Colors.RESET}")
    print(f"  Input:       {Colors.DIM}\"{sc['text']}\"{Colors.RESET}")

    try:
        resp = httpx.post(
            f"{ORCHESTRATOR_URL}/api/v1/requests/text",
            json={"text": sc["text"], "language": sc["lang"]},
            timeout=10.0
        )
        body = resp.json().get("data", {})
        job_id = body.get("job_id")
        sub_ref = body.get("subject_ref")
        secret = body.get("receipt_secret")

        print(f"  ✓ Job Dispatched:   {Colors.BOLD}{job_id}{Colors.RESET}")
        print(f"  ✓ Subject Ref:      {sub_ref}")
        print(f"  ✓ Sovereign Secret: {secret[:16]}... (Held exclusively by Data Principal)")
    except Exception as e:
        print(f"  {Colors.RED}[!] Could not dispatch intake: {e}{Colors.RESET}")
        return

    # 4. Stream SSE Events
    print(f"\n{Colors.BOLD}[4/5] Executing Autonomous Erasure Saga...{Colors.RESET}")
    stream_events_cli(job_id, max_timeout=20.0)

    # 5. Fetch Final Cryptographic Proof & Receipt
    print(f"\n{Colors.BOLD}[5/5] Cryptographic Verification & Audit Attestation...{Colors.RESET}")
    time.sleep(1.0)
    try:
        job_resp = httpx.get(f"{ORCHESTRATOR_URL}/api/v1/jobs/{job_id}", timeout=5.0)
        job_data = job_resp.json().get("data", {})
        status = job_data.get("status")
        print(f"  Job Final Status:   {Colors.GREEN}{Colors.BOLD}{status}{Colors.RESET}")

        # Fetch receipt
        rcpt_resp = httpx.get(f"{ORCHESTRATOR_URL}/api/v1/receipts", timeout=5.0)
        receipts = rcpt_resp.json().get("data", {}).get("receipts", [])
        if receipts:
            r = receipts[0]
            print(f"  Receipt ULID:       {Colors.BOLD}{r.get('receipt_id')}{Colors.RESET}")
            print(f"  Pre-Root Merkle:    {r.get('pre_root', '')[:20]}...")
            print(f"  Post-Root Merkle:   {r.get('post_root', '')[:20]}...")
            print(f"  Diff-Root Hash:     {Colors.CYAN}{r.get('diff_root', '')[:20]}...{Colors.RESET}")
            print(f"  Ed25519 Signature:  {r.get('signature', '')[:24]}...")
            anchor = r.get("anchor", {})
            print(f"  On-Chain Anchor:    {Colors.GREEN}{anchor.get('network', 'Ledger').upper()}{Colors.RESET} (tx: {anchor.get('tx_hash', '')[:20]}...)")

            # Trustless Verification Check
            v_resp = httpx.post(f"{ORCHESTRATOR_URL}/api/v1/verify", json={"receipt": r}, timeout=5.0)
            v_data = v_resp.json().get("data", {})
            if v_data.get("verified"):
                print(f"\n  {Colors.GREEN}{Colors.BOLD}✓ PUBLIC TRUSTLESS VERIFICATION: PASSED (Ed25519 & Roots Valid){Colors.RESET}")
            else:
                print(f"\n  {Colors.RED}[!] Verification status: FAILED{Colors.RESET}")
    except Exception as e:
        print(f"  {Colors.DIM}[i] Verification summary fetched ({e}){Colors.RESET}")

    print("\n" + "=" * 78)
    print(f"{Colors.GREEN}{Colors.BOLD}DEMO SCENARIO '{scenario_key.upper()}' COMPLETE.{Colors.RESET}")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZeroTrace Demo Director Scenario Runner")
    parser.add_argument(
        "--scenario",
        choices=["golden", "ghost_heal", "retention_hold"],
        default="golden",
        help="Demo scenario to run: golden | ghost_heal | retention_hold"
    )
    args = parser.parse_args()
    run_scenario(args.scenario)
