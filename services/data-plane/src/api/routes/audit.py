"""Audit and per-attack endpoints."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from src.api.deps import require_service_key
from src.api.schemas import ApiResponse, AttackFinding, AuditRequest, AuditResponse, CollateralIntegrity
from src.audit.attack_library import ATTACK_MAP, attack_collateral, run_audit
from src.core.logging import get_logger

router = APIRouter()
logger = get_logger("audit_routes")


@router.post("/v1/audit/run", dependencies=[Depends(require_service_key)])
async def run_audit_endpoint(req: AuditRequest):
    idents = [i.model_dump() for i in req.identifiers]
    result = await asyncio.to_thread(run_audit, req.job_id, idents, req.attacks)

    findings = [
        AttackFinding(
            attack_type=f.get("attack_type", ""),
            description=f.get("description", ""),
            verdict=f.get("verdict", "ERROR"),
            evidence_summary=f.get("evidence_summary", []),
            match_count=f.get("match_count", 0),
            duration_ms=f.get("duration_ms", 0),
        )
        for f in result["findings"]
    ]

    ci = result.get("collateral_integrity", {})

    return ApiResponse(data=AuditResponse(
        verdict=result["verdict"],
        findings=findings,
        collateral_integrity=CollateralIntegrity(
            rows_compared=ci.get("rows_compared", 0),
            checksum_match=ci.get("checksum_match", True),
            other_subjects_affected=ci.get("other_subjects_affected", 0),
        ),
        residual_locations=result.get("residual_locations", []),
    ).model_dump())


@router.post("/v1/attack/{attack_type}", dependencies=[Depends(require_service_key)])
async def run_single_attack(attack_type: str, body: AuditRequest):
    idents = [i.model_dump() for i in body.identifiers]

    if attack_type == "collateral":
        result = await asyncio.to_thread(attack_collateral, body.job_id)
    elif attack_type in ATTACK_MAP:
        result = await asyncio.to_thread(ATTACK_MAP[attack_type], idents)
    else:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={"code": "VALIDATION_ERROR", "message": f"Unknown attack type: {attack_type}"},
        )

    return ApiResponse(data=result)
