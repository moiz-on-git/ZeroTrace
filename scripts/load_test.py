"""
ZeroTrace Production Load Test.
Proves the orchestrator can handle concurrent erasure requests at production scale.
Fires N concurrent intake requests and measures p50/p95/p99 latency + throughput.
Usage: python scripts/load_test.py --concurrency 20 --requests 100
"""

from __future__ import annotations
import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from typing import List

import httpx

BASE_URL = os.environ.get("ZT_ORCHESTRATOR_URL", "http://localhost:8001")
DEMO_TOKEN: str = ""


async def get_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(f"{BASE_URL}/api/v1/auth/demo-login", json={"role": "dpo"})
    return resp.json()["data"]["token"]


async def fire_single_request(client: httpx.AsyncClient, idx: int) -> dict:
    start = time.perf_counter()
    try:
        resp = await client.post(
            f"{BASE_URL}/api/v1/requests/text",
            json={
                "text": f"I withdraw consent. Phone: +91 9876{idx:06d}.",
                "language": "en-IN"
            },
            headers={"Authorization": f"Bearer {DEMO_TOKEN}"},
            timeout=15.0
        )
        elapsed = (time.perf_counter() - start) * 1000
        if resp.status_code == 202:
            data = resp.json()["data"]
            return {"ok": True, "latency_ms": elapsed, "job_id": data["job_id"], "status": data["status"]}
        else:
            return {"ok": False, "latency_ms": elapsed, "error": resp.text[:200]}
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return {"ok": False, "latency_ms": elapsed, "error": str(e)}


async def run_load_test(concurrency: int, total_requests: int):
    global DEMO_TOKEN
    print("=" * 70)
    print("ZEROTRACE PRODUCTION LOAD TEST")
    print(f"  Target: {BASE_URL}")
    print(f"  Total requests: {total_requests}  |  Concurrency: {concurrency}")
    print("=" * 70)

    async with httpx.AsyncClient() as client:
        try:
            DEMO_TOKEN = await get_token(client)
            print(f"[AUTH] JWT token acquired.\n")
        except Exception as e:
            print(f"[WARN] Could not get auth token ({e}). Proceeding without auth.")

    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_request(client: httpx.AsyncClient, idx: int) -> dict:
        async with semaphore:
            return await fire_single_request(client, idx)

    wall_start = time.perf_counter()
    async with httpx.AsyncClient() as client:
        tasks = [bounded_request(client, i) for i in range(total_requests)]
        results = await asyncio.gather(*tasks)
    wall_elapsed = time.perf_counter() - wall_start

    ok_results = [r for r in results if r["ok"]]
    fail_results = [r for r in results if not r["ok"]]
    latencies = [r["latency_ms"] for r in ok_results]

    print(f"\n{'='*70}")
    print("LOAD TEST RESULTS")
    print(f"{'='*70}")
    print(f"  Total requests:   {total_requests}")
    print(f"  Successful:       {len(ok_results)} ({100*len(ok_results)/total_requests:.1f}%)")
    print(f"  Failed:           {len(fail_results)}")
    print(f"  Wall-clock time:  {wall_elapsed:.2f}s")
    print(f"  Throughput:       {len(ok_results)/wall_elapsed:.1f} req/s")

    if latencies:
        latencies_sorted = sorted(latencies)
        p50 = statistics.median(latencies_sorted)
        p95 = latencies_sorted[int(0.95 * len(latencies_sorted))]
        p99 = latencies_sorted[int(0.99 * len(latencies_sorted))]
        print(f"\n  Latency (ms):")
        print(f"    min:  {min(latencies):.1f}")
        print(f"    p50:  {p50:.1f}")
        print(f"    p95:  {p95:.1f}")
        print(f"    p99:  {p99:.1f}")
        print(f"    max:  {max(latencies):.1f}")

    if fail_results:
        print(f"\n  Sample failures:")
        for f in fail_results[:3]:
            print(f"    -> {f['error']}")

    print(f"\n{'='*70}")

    # SLO assertions
    slo_pass = True
    if len(ok_results) / total_requests < 0.99:
        print("[WARN] SLO BREACH: Success rate < 99%")
        slo_pass = False
    if latencies and p95 > 2000:
        print(f"[WARN] SLO BREACH: p95 latency {p95:.0f}ms > 2000ms target")
        slo_pass = False
    if slo_pass:
        print("[PASS] All SLOs met: >=99% success rate, p95 < 2000ms")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZeroTrace Production Load Test")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--requests", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(run_load_test(args.concurrency, args.requests))
