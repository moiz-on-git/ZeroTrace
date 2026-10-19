"""
Event emission helpers — shared event schema for job progress.
Events are written to: Postgres job_events table + Redis pub/sub channel.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger("events")
cfg = get_settings()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_event(
    job_id: str,
    seq: int,
    stage: str,
    kind: str,
    layer: str,
    message: str,
    data: dict | None = None,
) -> dict:
    """Build a standard event dict (no PII)."""
    return {
        "seq": seq,
        "ts": _now_iso(),
        "job_id": job_id,
        "stage": stage,
        "kind": kind,
        "layer": layer,
        "message": message,
        "data": data or {},
    }


class EventEmitter:
    """
    Emits events to Postgres and Redis for a specific job.
    Thread-safe seq counter.
    """

    def __init__(self, job_id: str):
        self.job_id = job_id
        self._seq = 0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    async def emit(
        self,
        stage: str,
        kind: str,
        layer: str,
        message: str,
        data: dict | None = None,
    ) -> dict:
        """Emit an event asynchronously."""
        from src.core.db import get_app_session
        from src.core.models import JobEvent
        from src.core.redis_client import get_async_queue

        seq = self._next_seq()
        event = make_event(self.job_id, seq, stage, kind, layer, message, data)

        # Write to Postgres
        try:
            async with get_app_session() as session:
                session.add(JobEvent(
                    seq=seq,
                    job_id=self.job_id,
                    stage=stage,
                    kind=kind,
                    layer=layer,
                    message=message,
                    data=data or {},
                ))
        except Exception as e:
            logger.warning("event.pg_write_failed", job_id=self.job_id, error=str(e))

        # Publish to Redis channel so SSE subscribers get it instantly
        try:
            r = get_async_queue()
            channel = f"zt:events:{self.job_id}"
            await r.publish(channel, json.dumps(event))
        except Exception as e:
            logger.warning("event.redis_publish_failed", job_id=self.job_id, error=str(e))

        return event

    def emit_sync(
        self,
        stage: str,
        kind: str,
        layer: str,
        message: str,
        data: dict | None = None,
    ) -> dict:
        """Synchronous emit for use inside PySpark / thread contexts."""
        import redis as syncredis

        seq = self._next_seq()
        event = make_event(self.job_id, seq, stage, kind, layer, message, data)

        try:
            r = syncredis.Redis(
                host=cfg.redis_host,
                port=cfg.redis_port,
                db=cfg.redis_queue_db,
                decode_responses=True,
                socket_timeout=5,
            )
            r.publish(f"zt:events:{self.job_id}", json.dumps(event))
        except Exception as e:
            logger.warning("event.sync_publish_failed", error=str(e))

        return event
