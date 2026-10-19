"""
Erasure Executor — orchestrates all three layers in parallel (vector + cache)
while keeping Iceberg sequential (order matters).

Job progress is persisted to Postgres at every checkpoint so crashes can resume.
Idempotent: re-running a completed step is a no-op.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from src.core.config import get_settings
from src.core.logging import get_logger
from src.erasure.cache_eraser import erase_cache
from src.erasure.crypto_eraser import destroy_data_key
from src.erasure.events import EventEmitter
from src.erasure.iceberg_eraser import erase_iceberg
from src.erasure.vector_eraser import erase_vectors

logger = get_logger("executor")
cfg = get_settings()


async def execute_erasure(
    job_id: str,
    plan_id: str,
    subject_ref: str,
    identifiers: list[dict],
    held_tables: set[str],
    mode: str = "both",          # both | crypto_only | physical_only
    ghost_miss: bool = False,    # demo flag: first pass skips semantic sweep
) -> dict:
    """
    Execute full erasure for a job.
    Returns aggregate metrics.
    """
    emitter = EventEmitter(job_id)
    all_metrics: dict[str, Any] = {}
    t0 = time.perf_counter()

    await _update_job_status(job_id, "EXECUTING")

    # ── Speed 1: Cryptographic kill-switch (instant) ──────────────────────────
    if mode in ("both", "crypto_only") and cfg.enable_crypto_shred:
        crypto_metrics = await destroy_data_key(job_id, subject_ref, emitter)
        all_metrics["crypto"] = crypto_metrics

    if mode == "crypto_only":
        await _update_job_status(job_id, "COMPLETED")
        return all_metrics

    # ── Speed 2: Physical eradication ────────────────────────────────────────
    # Iceberg must run sequentially (step order is enforced).
    # Vector and cache can run in parallel with each other AFTER Iceberg step 2
    # (they don't share any state with the lake).

    await emitter.emit("ERASE_ICEBERG", "started", "iceberg",
                       "Physical lake erasure beginning")

    # Run Iceberg in a thread (PySpark is blocking)
    loop = asyncio.get_event_loop()
    iceberg_task = loop.run_in_executor(
        None,
        _run_iceberg_sync,
        job_id, subject_ref, identifiers, held_tables, emitter,
    )

    # Run vector + cache in parallel
    vector_task = asyncio.create_task(
        asyncio.to_thread(
            _run_vector_sync,
            job_id, subject_ref, identifiers, emitter, ghost_miss,
        )
    )
    cache_task = asyncio.create_task(
        asyncio.to_thread(
            _run_cache_sync,
            job_id, subject_ref, identifiers, emitter,
        )
    )

    # Wait for all three
    iceberg_metrics, vector_metrics, cache_metrics = await asyncio.gather(
        iceberg_task, vector_task, cache_task, return_exceptions=True
    )

    if isinstance(iceberg_metrics, Exception):
        logger.error("executor.iceberg_failed", error=str(iceberg_metrics))
        await emitter.emit("ERASE_ICEBERG", "failed", "iceberg",
                           f"Iceberg erasure failed: {iceberg_metrics}")
        iceberg_metrics = {"error": str(iceberg_metrics)}

    if isinstance(vector_metrics, Exception):
        logger.error("executor.vector_failed", error=str(vector_metrics))
        vector_metrics = {"error": str(vector_metrics)}

    if isinstance(cache_metrics, Exception):
        logger.error("executor.cache_failed", error=str(cache_metrics))
        cache_metrics = {"error": str(cache_metrics)}

    all_metrics.update({
        "iceberg": iceberg_metrics,
        "vector": vector_metrics,
        "cache": cache_metrics,
    })

    elapsed = time.perf_counter() - t0
    all_metrics["total_duration_ms"] = round(elapsed * 1000, 0)

    await emitter.emit("ERASE_ICEBERG", "metric", "system",
                       f"All three layers erased in {elapsed:.1f}s",
                       {"duration_ms": all_metrics["total_duration_ms"]})

    await _update_job_status(job_id, "AUDITING")
    return all_metrics


def _run_iceberg_sync(job_id, subject_ref, identifiers, held_tables, emitter):
    return erase_iceberg(
        job_id=job_id,
        subject_ref=subject_ref,
        identifiers=identifiers,
        held_tables=held_tables,
        emitter=emitter,
    )


def _run_vector_sync(job_id, subject_ref, identifiers, emitter, skip_sweep):
    return erase_vectors(
        job_id=job_id,
        subject_ref=subject_ref,
        identifiers=identifiers,
        emitter=emitter,
        skip_semantic_sweep=skip_sweep,
    )


def _run_cache_sync(job_id, subject_ref, identifiers, emitter):
    return erase_cache(
        job_id=job_id,
        subject_ref=subject_ref,
        identifiers=identifiers,
        emitter=emitter,
    )


async def _update_job_status(job_id: str, status: str) -> None:
    try:
        from src.core.db import get_app_session
        from src.core.models import ErasureJob
        from sqlalchemy import select

        async with get_app_session() as session:
            result = await session.execute(
                select(ErasureJob).where(ErasureJob.job_id == job_id)
            )
            job = result.scalar_one_or_none()
            if job:
                job.status = status
                if status in ("COMPLETED", "COMPLETED_WITH_HOLDS", "FAILED"):
                    job.completed_at = datetime.now(timezone.utc)
    except Exception as e:
        logger.warning("executor.status_update_failed", job_id=job_id, error=str(e))
