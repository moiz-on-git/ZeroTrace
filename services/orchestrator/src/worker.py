"""
ZeroTrace ARQ Distributed Job Worker.
Processes heavy asynchronous erasure sagas, cryptographic key shredding,
and adversarial audit loops in the background on Redis db1.
"""

from __future__ import annotations
import asyncio
from typing import Any, Dict, Optional
from arq.connections import RedisSettings
from core.config import settings
from core.logging import logger
from models.database import async_session, init_db
from services.orchestration import JobOrchestrator


async def execute_erasure_saga_task(
    ctx: Dict[Any, Any],
    job_id: str,
    channel: str = "text",
    raw_text: Optional[str] = None,
    audio_bytes: Optional[bytes] = None,
    language_hint: Optional[str] = None,
    auto_approve: bool = True
) -> Dict[str, Any]:
    """
    ARQ worker entrypoint for executing an autonomous erasure and proof saga.
    """
    logger.info("arq_worker_starting_saga", job_id=job_id, channel=channel)
    async with async_session() as session:
        orchestrator = JobOrchestrator()
        result = await orchestrator.execute_job_saga(
            session=session,
            job_id=job_id,
            channel=channel,
            raw_text=raw_text,
            audio_bytes=audio_bytes,
            language_hint=language_hint,
            auto_approve=auto_approve
        )
    logger.info("arq_worker_saga_completed", job_id=job_id, status=result.get("status"))
    return result


async def startup(ctx: Dict[Any, Any]) -> None:
    logger.info("arq_worker_booting", redis=settings.REDIS_URL)
    await init_db()


async def shutdown(ctx: Dict[Any, Any]) -> None:
    logger.info("arq_worker_shutting_down")


class WorkerSettings:
    functions = [execute_erasure_saga_task]
    on_startup = startup
    on_shutdown = shutdown
    # Parse redis URL for ARQ
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 300  # 5 minutes per job
