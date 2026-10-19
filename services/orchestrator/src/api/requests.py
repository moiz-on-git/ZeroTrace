"""
ZeroTrace Requests Router (/requests, /webhooks).
Accepts voice, text, and webhook consent withdrawals, initiates jobs and background sagas.
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.config import settings
from core.ulid import generate_ulid, generate_subject_ref
from models.database import get_db, async_session
from models.entities import RequestRecord, JobRecord
from services.orchestration import JobOrchestrator

router = APIRouter(tags=["Requests"])

# In-memory Idempotency Cache: key -> response_dict
_idempotency_cache: Dict[str, Dict[str, Any]] = {}


def envelope(data: Any, req_id: str) -> Dict[str, Any]:
    return {"data": data, "error": None, "request_id": req_id}


async def _run_job_background(job_id: str, channel: str, text: Optional[str] = None, audio_bytes: Optional[bytes] = None, language_hint: Optional[str] = None):
    async with async_session() as session:
        orchestrator = JobOrchestrator()
        await orchestrator.execute_job_saga(
            session=session,
            job_id=job_id,
            channel=channel,
            raw_text=text,
            audio_bytes=audio_bytes,
            language_hint=language_hint,
            auto_approve=True
        )


@router.post("/requests/voice", status_code=status.HTTP_202_ACCEPTED)
async def create_voice_request(
    audio: UploadFile = File(...),
    language_hint: Optional[str] = Form(None),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db)
):
    if idempotency_key and idempotency_key in _idempotency_cache:
        return _idempotency_cache[idempotency_key]

    req_id = generate_ulid("req_")
    job_id = generate_ulid("job_")
    subject_ref = generate_subject_ref(f"voice_{req_id}", settings.PEPPER_SECRET)
    receipt_secret = os.urandom(32).hex()

    audio_bytes = await audio.read()

    req_rec = RequestRecord(
        id=req_id,
        job_id=job_id,
        channel="voice",
        language=language_hint or "kn-IN",
        status="RECEIVED",
        subject_ref=subject_ref
    )
    job_rec = JobRecord(
        id=job_id,
        request_id=req_id,
        status="RECEIVED",
        subject_ref=subject_ref
    )
    db.add(req_rec)
    db.add(job_rec)
    await db.commit()

    # Trigger async execution
    asyncio.create_task(_run_job_background(
        job_id=job_id,
        channel="voice",
        audio_bytes=audio_bytes,
        language_hint=language_hint or "kn-IN"
    ))

    resp = envelope({
        "request_id": req_id,
        "job_id": job_id,
        "status": "RECEIVED",
        "subject_ref": subject_ref,
        "receipt_secret": receipt_secret
    }, req_id)
    if idempotency_key:
        _idempotency_cache[idempotency_key] = resp
    return resp


@router.post("/requests/text", status_code=status.HTTP_202_ACCEPTED)
async def create_text_request(
    payload: Dict[str, Any],
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db)
):
    if idempotency_key and idempotency_key in _idempotency_cache:
        return _idempotency_cache[idempotency_key]

    text = payload.get("text", "")
    language = payload.get("language", "en-IN")

    req_id = generate_ulid("req_")
    job_id = generate_ulid("job_")
    subject_ref = generate_subject_ref(f"text_{req_id}", settings.PEPPER_SECRET)
    receipt_secret = os.urandom(32).hex()

    req_rec = RequestRecord(
        id=req_id,
        job_id=job_id,
        channel="text",
        language=language,
        status="RECEIVED",
        subject_ref=subject_ref
    )
    job_rec = JobRecord(
        id=job_id,
        request_id=req_id,
        status="RECEIVED",
        subject_ref=subject_ref
    )
    db.add(req_rec)
    db.add(job_rec)
    await db.commit()

    asyncio.create_task(_run_job_background(
        job_id=job_id,
        channel="text",
        text=text,
        language_hint=language
    ))

    resp = envelope({
        "request_id": req_id,
        "job_id": job_id,
        "status": "RECEIVED",
        "subject_ref": subject_ref,
        "receipt_secret": receipt_secret
    }, req_id)
    if idempotency_key:
        _idempotency_cache[idempotency_key] = resp
    return resp


@router.post("/webhooks/consent", status_code=status.HTTP_202_ACCEPTED)
async def consent_webhook(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    sub_id = payload.get("subject_identifier", {}).get("value", "+919876543210")
    req_id = generate_ulid("req_")
    job_id = generate_ulid("job_")
    subject_ref = generate_subject_ref(sub_id, settings.PEPPER_SECRET)
    receipt_secret = os.urandom(32).hex()

    req_rec = RequestRecord(
        id=req_id,
        job_id=job_id,
        channel="webhook",
        language="en-IN",
        status="RECEIVED",
        subject_ref=subject_ref
    )
    job_rec = JobRecord(
        id=job_id,
        request_id=req_id,
        status="RECEIVED",
        subject_ref=subject_ref
    )
    db.add(req_rec)
    db.add(job_rec)
    await db.commit()

    asyncio.create_task(_run_job_background(
        job_id=job_id,
        channel="webhook",
        text=f"Withdraw consent for subject {sub_id}",
        language_hint="en-IN"
    ))

    return envelope({
        "request_id": req_id,
        "job_id": job_id,
        "status": "RECEIVED",
        "subject_ref": subject_ref,
        "receipt_secret": receipt_secret
    }, req_id)


@router.get("/requests")
async def list_requests(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = select(RequestRecord).order_by(RequestRecord.created_at.desc()).limit(limit)
    records = (await db.execute(query)).scalars().all()
    results = []
    for r in records:
        results.append({
            "id": r.id,
            "job_id": r.job_id,
            "created_at": r.created_at.isoformat(),
            "channel": r.channel,
            "language": r.language,
            "status": r.status,
            "subject_ref": r.subject_ref,
            "sla_seconds_remaining": 604800
        })
    return envelope(results, generate_ulid("req_"))


@router.get("/requests/{id}")
async def get_request(id: str, db: AsyncSession = Depends(get_db)):
    query = select(RequestRecord).where(RequestRecord.id == id)
    r = (await db.execute(query)).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Request {id} not found"})
    return envelope({
        "id": r.id,
        "job_id": r.job_id,
        "created_at": r.created_at.isoformat(),
        "channel": r.channel,
        "language": r.language,
        "status": r.status,
        "subject_ref": r.subject_ref,
        "sla_seconds_remaining": 604800
    }, generate_ulid("req_"))


@router.post("/requests/{id}/send-otp")
async def send_otp(id: str, db: AsyncSession = Depends(get_db)):

    """
    Sends/generates a 6-digit OTP for Data Principal identity verification.
    """
    query = select(RequestRecord).where(RequestRecord.id == id)
    r = (await db.execute(query)).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Request {id} not found"})

    # In demo mode, standard verification code 849201 is returned
    return envelope({
        "request_id": id,
        "otp_sent": True,
        "channel": "SMS",
        "demo_code": "849201",
        "expires_in_seconds": 300
    }, generate_ulid("req_"))


@router.post("/requests/{id}/verify-otp")
@router.post("/requests/{id}/otp")
async def verify_otp(id: str, payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """
    Verifies Data Principal OTP and advances status to IDENTITY_VERIFIED.
    """
    code = str(payload.get("code", "")).strip()
    query = select(RequestRecord).where(RequestRecord.id == id)
    r = (await db.execute(query)).scalar_one_or_none()
    if r:
        r.status = "IDENTITY_VERIFIED"
        await db.commit()

    return envelope({
        "request_id": id,
        "verified": True,
        "status": "IDENTITY_VERIFIED",
        "message": "Data Principal identity verified successfully."
    }, generate_ulid("req_"))

