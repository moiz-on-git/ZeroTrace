"""
ZeroTrace Auth Router (/auth, /me).
"""

from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, Depends
from core.auth import create_access_token, get_current_user
from core.ulid import generate_ulid

router = APIRouter(tags=["Auth"])


def envelope(data: Any, req_id: str) -> Dict[str, Any]:
    return {"data": data, "error": None, "request_id": req_id}


@router.post("/auth/demo-login")
async def demo_login(payload: Dict[str, Any]):
    role = payload.get("role", "dpo")
    user_id = f"usr_{role}_{generate_ulid()[:10]}"
    token = create_access_token(role=role, user_id=user_id)
    return envelope({
        "token": token,
        "role": role,
        "user": f"{role}@kaveri-finserv.internal"
    }, generate_ulid("req_"))


@router.get("/me")
async def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    return envelope({
        "id": user.get("sub"),
        "role": user.get("role"),
        "permissions": user.get("permissions", [])
    }, generate_ulid("req_"))
