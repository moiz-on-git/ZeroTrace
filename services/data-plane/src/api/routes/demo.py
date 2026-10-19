"""
Demo support endpoints: seed, reset, naive-delete, subjects, scenario flags.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from src.api.deps import require_service_key
from src.api.schemas import (
    ApiResponse,
    ScenarioRequest,
    SeedRequest,
    SeedResponse,
    SubjectDescriptor,
)
from src.core.config import get_settings
from src.core.logging import get_logger
from src.seed.subjects import ALL_SUBJECTS, HERO

router = APIRouter()
logger = get_logger("demo_routes")
cfg = get_settings()


@router.post("/v1/demo/seed", dependencies=[Depends(require_service_key)])
async def seed_demo(req: SeedRequest):
    from src.seed.orchestrator import seed

    result = await asyncio.to_thread(seed, req.profile)
    return ApiResponse(data=SeedResponse(
        profile=result["profile"],
        elapsed_s=result["elapsed_s"],
        tables=result["tables"],
        vectors=result["vectors"],
        cache=result["cache"],
    ).model_dump())


@router.post("/v1/demo/reset", dependencies=[Depends(require_service_key)])
async def reset_demo():
    from src.seed.orchestrator import reset

    result = await asyncio.to_thread(reset, "showtime")
    return ApiResponse(data=result)


@router.post("/v1/demo/naive-delete", dependencies=[Depends(require_service_key)])
async def naive_delete(body: dict = {}):
    """
    Performs a naive DELETE like a typical company would —
    leaving the data in old Parquet files, old snapshots, and the cache.
    The Adversary Console can then immediately demonstrate resurrection.
    """
    from src.core.spark_session import get_spark
    from src.erasure.events import EventEmitter

    job_id = body.get("job_id", "demo_naive_000")
    identifiers = body.get("identifiers", [
        {"type": "customer_id", "value": HERO.customer_id},
        {"type": "phone", "value": HERO.phone},
        {"type": "email", "value": HERO.email},
    ])

    emitter = EventEmitter(job_id)
    from src.erasure.iceberg_eraser import erase_iceberg
    from src.seed.iceberg_writer import TABLE_TAGS

    # Run with naive_order=True — orphan removal BEFORE snapshot expiry = 0 bytes removed
    metrics = await asyncio.to_thread(
        erase_iceberg,
        job_id,
        "demo_naive_ref",
        identifiers,
        set(),          # no holds
        emitter,
        True,           # naive_order=True
    )

    return ApiResponse(data={
        "message": (
            "Naive DELETE executed. Data rows are marked deleted but "
            "original Parquet files remain on disk. "
            "Time-travel, raw Parquet, bucket grep and the Support Copilot "
            "will all still find the subject's data."
        ),
        "metrics": metrics,
        "trap_explanation": (
            "Orphan file removal ran BEFORE snapshot expiry — "
            "deleted 0 bytes because old snapshots still reference the files."
        ),
    })


@router.get("/v1/demo/subjects", dependencies=[Depends(require_service_key)])
async def get_subjects():
    descriptors = []
    for subj in ALL_SUBJECTS:
        p = subj.phone
        masked_phone = f"+91 {p[:3]}••• ••{p[-3:]}"
        e = subj.email
        user, domain = e.split("@")
        masked_email = f"{user[:2]}{'•' * (len(user) - 2)}@{domain}"
        descriptors.append(SubjectDescriptor(
            customer_id=subj.customer_id,
            display_name=subj.full_name,
            masked_phone=masked_phone,
            masked_email=masked_email,
            subject_ref=subj.subject_ref(),
            is_hero=subj.is_hero,
            decoy_note=subj.decoy_note,
        ).model_dump())

    return ApiResponse(data={"subjects": descriptors})


@router.post("/v1/demo/scenario", dependencies=[Depends(require_service_key)])
async def set_scenario(req: ScenarioRequest):
    """Set demo scenario flags (runtime override)."""
    changes = {}
    if req.ghost_miss is not None:
        # Dynamically update the config flag (for demo only)
        import src.core.config as _cfg_mod
        _cfg_mod.get_settings.cache_clear()
        import os
        os.environ["ZT_DEMO_GHOST_MISS"] = str(req.ghost_miss).lower()
        changes["ghost_miss"] = req.ghost_miss

    if req.auto_approve is not None:
        import os
        os.environ["ZT_DEMO_AUTO_APPROVE"] = str(req.auto_approve).lower()
        changes["auto_approve"] = req.auto_approve

    return ApiResponse(data={"applied": changes, "message": "Scenario flags updated"})
