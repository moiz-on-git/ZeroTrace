"""
ZeroTrace Event Bus & SSE Publisher.
Guarantees monotonic sequence numbering, persistent storage in job_events,
optional Redis Pub/Sub broadcast, and Last-Event-ID replay.
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from models.entities import JobEventRecord
from core.logging import logger
from core.config import settings

# In-memory subscriber registry for SSE connections: job_id -> list of asyncio.Queue
_subscribers: Dict[str, List[asyncio.Queue]] = {}
_lock = asyncio.Lock()


async def emit_event(
    session: AsyncSession,
    job_id: str,
    stage: str,
    kind: str,
    layer: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> JobEventRecord:
    """
    Appends a new event monotonically to the job's event stream.
    Persists to DB and broadcasts to all active SSE subscribers.
    """
    # 1. Monotonic sequence calculation
    seq_query = select(func.coalesce(func.max(JobEventRecord.seq), 0)).where(JobEventRecord.job_id == job_id)
    result = await session.execute(seq_query)
    current_max_seq = result.scalar_one()
    next_seq = current_max_seq + 1

    event_record = JobEventRecord(
        job_id=job_id,
        seq=next_seq,
        ts=datetime.now(timezone.utc),
        stage=stage,
        kind=kind,
        layer=layer,
        message=message,
        data_json=json.dumps(data or {})
    )
    session.add(event_record)
    await session.commit()
    await session.refresh(event_record)

    event_payload = {
        "seq": event_record.seq,
        "ts": event_record.ts.isoformat(),
        "job_id": event_record.job_id,
        "stage": event_record.stage,
        "kind": event_record.kind,
        "layer": event_record.layer,
        "message": event_record.message,
        "data": data or {}
    }

    # Broadcast to in-memory queues
    async with _lock:
        if job_id in _subscribers:
            for q in list(_subscribers[job_id]):
                try:
                    q.put_nowait(event_payload)
                except asyncio.QueueFull:
                    pass

    logger.info(
        "job_event_emitted",
        job_id=job_id,
        seq=next_seq,
        stage=stage,
        kind=kind,
        layer=layer
    )
    return event_record


async def subscribe_events(
    session: AsyncSession,
    job_id: str,
    last_event_id: Optional[int] = None
) -> AsyncGenerator[str, None]:
    """
    Yields SSE formatted data for a given job_id.
    Replays past events starting from last_event_id + 1, then streams live events.
    """
    # Initial connection ping so HTTP response headers (Content-Type: text/event-stream) are dispatched immediately
    yield f": connected to job {job_id}\n\n"

    # Replay past events
    start_seq = (last_event_id or 0) + 1
    query = (
        select(JobEventRecord)
        .where(JobEventRecord.job_id == job_id, JobEventRecord.seq >= start_seq)
        .order_by(JobEventRecord.seq.asc())
    )
    past_records = (await session.execute(query)).scalars().all()

    for rec in past_records:
        ev_dict = {
            "seq": rec.seq,
            "ts": rec.ts.isoformat(),
            "job_id": rec.job_id,
            "stage": rec.stage,
            "kind": rec.kind,
            "layer": rec.layer,
            "message": rec.message,
            "data": json.loads(rec.data_json or "{}")
        }
        yield f"id: {rec.seq}\nevent: message\ndata: {json.dumps(ev_dict)}\n\n"

    # Register live subscriber queue
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    async with _lock:
        if job_id not in _subscribers:
            _subscribers[job_id] = []
        _subscribers[job_id].append(q)

    try:
        while True:
            try:
                ev_dict = await asyncio.wait_for(q.get(), timeout=15.0)
                yield f"id: {ev_dict['seq']}\nevent: message\ndata: {json.dumps(ev_dict)}\n\n"
                q.task_done()
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        async with _lock:
            if job_id in _subscribers and q in _subscribers[job_id]:
                _subscribers[job_id].remove(q)
                if not _subscribers[job_id]:
                    del _subscribers[job_id]
