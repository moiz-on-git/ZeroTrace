"""
Erasure endpoints: plan, execute (async), job status, SSE events, remediate.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from src.api.deps import require_service_key
from src.api.schemas import (
    ApiResponse,
    BlastRadiusOut,
    CostEstimateOut,
    ErasureStepOut,
    ExecuteRequest,
    ExecuteResponse,
    JobStatusResponse,
    ManifestItem,
    ManifestRequest,
    ManifestResponse,
    PlanRequest,
    PlanResponse,
    RemediateRequest,
    RemediateResponse,
)
from src.core.config import get_settings
from src.core.db import get_app_session
from src.core.logging import get_logger
from src.core.models import ErasureJob, JobEvent, StateManifestItem
from src.erasure.planner import build_plan
from src.erasure.executor import execute_erasure

router = APIRouter()
logger = get_logger("erasure_routes")
cfg = get_settings()


# ── Plan ─────────────────────────────────────────────────────────────────────

@router.post("/v1/erasure/plan", dependencies=[Depends(require_service_key)])
async def plan_erasure(req: PlanRequest):
    holds_dicts = [h.model_dump() for h in req.holds]
    idents_dicts = [i.model_dump() for i in req.identifiers]

    plan = await asyncio.to_thread(
        build_plan,
        req.job_id,
        req.subject_ref,
        idents_dicts,
        holds_dicts,
    )

    steps_out = [
        ErasureStepOut(
            step_id=s.step_id,
            layer=s.layer,
            action=s.action,
            target=s.target,
            est_rows=s.est_rows,
            est_files=s.est_files,
            est_bytes=s.est_bytes,
            est_cost_inr=s.est_cost_inr,
            order=s.order,
            parallel_group=s.parallel_group,
        )
        for s in plan.steps
    ]

    resp = PlanResponse(
        plan_id=plan.plan_id,
        job_id=plan.job_id,
        steps=steps_out,
        blast_radius=BlastRadiusOut(
            files_total=plan.blast_radius.files_total,
            files_targeted=plan.blast_radius.files_targeted,
            partitions_total=plan.blast_radius.partitions_total,
            partitions_targeted=plan.blast_radius.partitions_targeted,
            bloom_false_positive_rate=plan.blast_radius.bloom_false_positive_rate,
        ),
        cost=CostEstimateOut(
            naive_inr=plan.cost.naive_inr,
            targeted_inr=plan.cost.targeted_inr,
            saving_pct=plan.cost.saving_pct,
            assumptions=plan.cost.assumptions,
        ),
        holds=plan.holds,
        warnings=plan.warnings,
        created_at=plan.created_at,
    )

    # Persist plan_id on the job
    async with get_app_session() as session:
        result = await session.execute(
            select(ErasureJob).where(ErasureJob.job_id == req.job_id)
        )
        job = result.scalar_one_or_none()
        if job:
            job.plan_id = plan.plan_id
            job.status = "PLANNED"

    return ApiResponse(data=resp.model_dump())


# ── Execute ───────────────────────────────────────────────────────────────────

@router.post("/v1/erasure/execute", dependencies=[Depends(require_service_key)], status_code=202)
async def execute(req: ExecuteRequest, background_tasks: BackgroundTasks):
    # Validate job exists
    async with get_app_session() as session:
        result = await session.execute(
            select(ErasureJob).where(ErasureJob.job_id == req.job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Job not found"})
        if job.status == "EXECUTING":
            raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Job already executing"})

        # Get identifiers from checkpoint
        idents = job.checkpoint.get("identifiers", []) if job.checkpoint else []
        held_tables = set(job.checkpoint.get("held_tables", [])) if job.checkpoint else set()
        subject_ref = job.subject_ref

    background_tasks.add_task(
        _run_erasure_background,
        req.job_id,
        req.plan_id,
        subject_ref,
        idents,
        held_tables,
        req.mode,
        cfg.demo_ghost_miss,
    )

    return ApiResponse(data=ExecuteResponse(
        job_id=req.job_id,
        status="EXECUTING",
        message="Erasure started asynchronously",
    ).model_dump())


async def _run_erasure_background(job_id, plan_id, subject_ref, idents, held_tables, mode, ghost_miss):
    try:
        await execute_erasure(
            job_id=job_id,
            plan_id=plan_id,
            subject_ref=subject_ref,
            identifiers=idents,
            held_tables=held_tables,
            mode=mode,
            ghost_miss=ghost_miss,
        )
    except Exception as e:
        logger.error("erasure.background_failed", job_id=job_id, error=str(e))
        async with get_app_session() as session:
            result = await session.execute(select(ErasureJob).where(ErasureJob.job_id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.status = "FAILED"
                job.error_message = str(e)


# ── Job Status ────────────────────────────────────────────────────────────────

@router.get("/v1/jobs/{job_id}", dependencies=[Depends(require_service_key)])
async def get_job(job_id: str):
    async with get_app_session() as session:
        result = await session.execute(
            select(ErasureJob).where(ErasureJob.job_id == job_id)
        )
        job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Job not found"})

    return ApiResponse(data=JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        plan_id=job.plan_id,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error_message=job.error_message,
        checkpoint=job.checkpoint,
    ).model_dump())


# ── SSE Event Stream ──────────────────────────────────────────────────────────

@router.get("/v1/jobs/{job_id}/events", dependencies=[Depends(require_service_key)])
async def job_events(job_id: str, request: Request):
    """Server-Sent Events stream for a job. Supports Last-Event-ID replay."""
    last_event_id = request.headers.get("Last-Event-ID")
    last_seq = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def event_generator() -> AsyncGenerator[str, None]:
        # First: replay missed events from Postgres
        async with get_app_session() as session:
            result = await session.execute(
                select(JobEvent)
                .where(JobEvent.job_id == job_id, JobEvent.seq > last_seq)
                .order_by(JobEvent.seq)
            )
            past_events = result.scalars().all()

        for evt in past_events:
            payload = json.dumps({
                "seq": evt.seq,
                "ts": evt.ts.isoformat(),
                "job_id": evt.job_id,
                "stage": evt.stage,
                "kind": evt.kind,
                "layer": evt.layer,
                "message": evt.message,
                "data": evt.data,
            })
            yield f"id: {evt.seq}\ndata: {payload}\n\n"

        # Then subscribe to Redis pub/sub for live events
        from src.core.redis_client import get_async_queue
        r = get_async_queue()
        pubsub = r.pubsub()
        await pubsub.subscribe(f"zt:events:{job_id}")

        try:
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break
                if message["type"] == "message":
                    data = message["data"]
                    try:
                        evt_data = json.loads(data)
                        seq = evt_data.get("seq", 0)
                        yield f"id: {seq}\ndata: {data}\n\n"
                        # Check if job is done
                        if evt_data.get("kind") in ("completed", "failed") and \
                           evt_data.get("stage") == "COMPLETE":
                            break
                    except Exception:
                        continue
        finally:
            await pubsub.unsubscribe(f"zt:events:{job_id}")
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Remediate ────────────────────────────────────────────────────────────────

@router.post("/v1/erasure/remediate", dependencies=[Depends(require_service_key)])
async def remediate(req: RemediateRequest, background_tasks: BackgroundTasks):
    """Targeted re-erasure of residual locations found by the audit."""
    async with get_app_session() as session:
        result = await session.execute(
            select(ErasureJob).where(ErasureJob.job_id == req.job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Job not found"})
        idents = job.checkpoint.get("identifiers", []) if job.checkpoint else []
        subject_ref = job.subject_ref

    from src.erasure.events import EventEmitter
    from src.erasure.vector_eraser import erase_vectors
    from src.erasure.cache_eraser import erase_cache

    async def _remediate():
        emitter = EventEmitter(req.job_id)
        for loc in req.residual_locations:
            attack_type = loc.get("attack_type", "")
            if attack_type in ("vector_lookup", "rag_prompt_injection"):
                await asyncio.to_thread(
                    erase_vectors,
                    req.job_id, subject_ref, idents, emitter, False
                )
            elif attack_type in ("cache_probe",):
                await asyncio.to_thread(
                    erase_cache,
                    req.job_id, subject_ref, idents, emitter
                )

    background_tasks.add_task(_remediate)

    return ApiResponse(data=RemediateResponse(
        job_id=req.job_id,
        remediated=len(req.residual_locations),
        message="Remediation started",
    ).model_dump())


# ── State Manifest ────────────────────────────────────────────────────────────

@router.post("/v1/state/manifest", dependencies=[Depends(require_service_key)])
async def state_manifest(req: ManifestRequest):
    """
    Build and return a canonical state manifest for Merkle proof construction.
    Pre = before erasure; Post = after erasure.
    """
    import hashlib as _hashlib
    from src.core.s3_client import iter_all_objects, sha256_of_object
    from src.seed.iceberg_writer import TABLE_SCHEMAS

    items: list[ManifestItem] = []

    # Iceberg files
    for obj in iter_all_objects(prefix="warehouse/"):
        key = obj["Key"]
        if not key.endswith(".parquet") and not key.endswith(".metadata.json"):
            continue
        try:
            content_hash = await asyncio.to_thread(sha256_of_object, key)
        except Exception:
            content_hash = _hashlib.sha256(key.encode()).hexdigest()

        # Object ID must be stable and contain no PII
        object_id = _hashlib.sha256(key.encode()).hexdigest()[:32]

        items.append(ManifestItem(
            layer="iceberg",
            object_id=object_id,
            content_hash=content_hash,
            in_scope=True,
            held=False,
        ))

    # Vector embeddings
    try:
        import psycopg
        pg_dsn = (
            f"host={cfg.pg_host} port={cfg.pg_port} "
            f"dbname={cfg.pg_db_rag} "
            f"user={cfg.pg_user} password={cfg.pg_password}"
        )
        with psycopg.connect(pg_dsn) as conn:
            cur = conn.execute(
                "SELECT chunk_id, content FROM embeddings ORDER BY chunk_id"
            )
            for chunk_id, content in cur.fetchall():
                content_hash = _hashlib.sha256(content.encode()).hexdigest()
                object_id = _hashlib.sha256(chunk_id.encode()).hexdigest()[:32]
                items.append(ManifestItem(
                    layer="vector",
                    object_id=object_id,
                    content_hash=content_hash,
                    in_scope=True,
                    held=False,
                ))
    except Exception as e:
        logger.warning("manifest.vector_failed", error=str(e))

    # Cache entries
    try:
        import redis as syncredis
        r = syncredis.Redis(
            host=cfg.redis_host, port=cfg.redis_port,
            db=cfg.redis_cache_db, decode_responses=True, socket_timeout=5,
        )
        for key in sorted(r.scan_iter("zt:cache:*")):
            val = r.get(key)
            if val:
                content_hash = _hashlib.sha256(val.encode()).hexdigest()
                object_id = _hashlib.sha256(key.encode()).hexdigest()[:32]
                items.append(ManifestItem(
                    layer="cache",
                    object_id=object_id,
                    content_hash=content_hash,
                    in_scope=True,
                    held=False,
                ))
    except Exception as e:
        logger.warning("manifest.cache_failed", error=str(e))

    # Save to DB for collateral tracking
    async with get_app_session() as session:
        for item in items:
            session.add(StateManifestItem(
                job_id=req.job_id,
                label=req.label,
                layer=item.layer,
                object_id=item.object_id,
                content_hash=item.content_hash,
                in_scope=item.in_scope,
                held=item.held,
            ))

    # Sort canonically for deterministic Merkle construction
    items.sort(key=lambda i: (i.layer, i.object_id))

    return ApiResponse(data=ManifestResponse(
        job_id=req.job_id,
        label=req.label,
        items=[i.model_dump() for i in items],
        item_count=len(items),
    ).model_dump())
