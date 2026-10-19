"""
FastAPI dependency injection helpers — auth, request IDs, etc.
Uses custom exception hierarchy for consistent error responses.
"""
from __future__ import annotations

from fastapi import Header, Request

from src.core.config import get_settings
from src.core.exceptions import InvalidServiceKeyError

cfg = get_settings()


async def require_service_key(
    x_service_key: str | None = Header(default=None, alias="X-Service-Key"),
) -> None:
    """
    Validate the service-to-service key.
    Raises InvalidServiceKeyError (→ 401 with structured envelope) if invalid.
    """
    if not x_service_key or x_service_key != cfg.service_key:
        raise InvalidServiceKeyError(
            message="Invalid or missing X-Service-Key header",
            details={"header": "X-Service-Key"},
        )


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "unknown")
