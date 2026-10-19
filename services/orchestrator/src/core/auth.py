"""
ZeroTrace JWT Authentication & Role-Based Access Control.
Roles: principal, dpo, auditor, admin.
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from core.config import settings

security_bearer = HTTPBearer(auto_error=False)

ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "principal": ["requests:create", "receipts:read", "verify:read"],
    "dpo": ["requests:read", "requests:approve", "requests:reject", "jobs:read", "lineage:read", "plan:read", "audit:read", "receipts:read"],
    "auditor": ["requests:read", "jobs:read", "audit:read", "receipts:read", "certificate:read", "verify:read"],
    "admin": ["*"]
}


def create_access_token(role: str, user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates signed JWT token with role claims.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(hours=24))
    payload = {
        "sub": user_id,
        "role": role,
        "permissions": ROLE_PERMISSIONS.get(role, []),
        "iat": now,
        "exp": expire,
        "iss": "zerotrace.orchestrator"
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates JWT token.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Access token has expired"}
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid authentication token"}
        )


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> Dict[str, Any]:
    """
    FastAPI dependency for authenticated endpoints.
    Allows demo bypass if credentials not provided in development mode.
    """
    if not credentials:
        if settings.ENV == "development":
            return {"sub": "usr_dev_dpo", "role": "dpo", "permissions": ROLE_PERMISSIONS["dpo"]}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Authorization header missing"}
        )
    return decode_access_token(credentials.credentials)


def require_role(allowed_roles: List[str]):
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)):
        role = current_user.get("role")
        if role not in allowed_roles and role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": f"Requires one of roles: {allowed_roles}"}
            )
        return current_user
    return role_checker
