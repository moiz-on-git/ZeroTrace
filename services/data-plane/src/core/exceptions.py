"""
Custom exception hierarchy with structured error codes.
Every exception maps to a specific HTTP status and error code.
Used by the global exception handler to produce consistent API responses.
"""
from __future__ import annotations

from typing import Any, Optional


class ZTError(Exception):
    """Base exception for all ZeroTrace Data Plane errors."""

    code: str = "INTERNAL"
    status_code: int = 500
    message: str = "An internal error occurred."

    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        status_code: Optional[int] = None,
    ):
        self.message = message or self.__class__.message
        self.details = details or {}
        if status_code:
            self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# ── 400 Bad Request ────────────────────────────────────────────────────────────

class ValidationError(ZTError):
    code = "VALIDATION_ERROR"
    status_code = 400
    message = "Request validation failed."


class InvalidIdentifierError(ZTError):
    code = "VALIDATION_ERROR"
    status_code = 400
    message = "Invalid identifier format."


# ── 401 Unauthorized ──────────────────────────────────────────────────────────

class UnauthorizedError(ZTError):
    code = "UNAUTHORIZED"
    status_code = 401
    message = "Authentication required."


class InvalidServiceKeyError(ZTError):
    code = "UNAUTHORIZED"
    status_code = 401
    message = "Invalid or missing X-Service-Key header."


# ── 403 Forbidden ──────────────────────────────────────────────────────────────

class ForbiddenError(ZTError):
    code = "FORBIDDEN"
    status_code = 403
    message = "You do not have permission to perform this action."


# ── 404 Not Found ──────────────────────────────────────────────────────────────

class NotFoundError(ZTError):
    code = "NOT_FOUND"
    status_code = 404
    message = "Resource not found."


class JobNotFoundError(NotFoundError):
    message = "Job not found."


# ── 409 Conflict ───────────────────────────────────────────────────────────────

class ConflictError(ZTError):
    code = "CONFLICT"
    status_code = 409
    message = "Resource already exists or is in a conflicting state."


class JobAlreadyRunningError(ConflictError):
    message = "Job is already executing."


# ── 422 Unprocessable Entity ──────────────────────────────────────────────────

class PolicyBlockedError(ZTError):
    code = "POLICY_BLOCKED"
    status_code = 422
    message = "Request blocked by retention policy."


# ── 429 Rate Limited ───────────────────────────────────────────────────────────

class RateLimitedError(ZTError):
    code = "RATE_LIMITED"
    status_code = 429
    message = "Too many requests. Please retry after the cooldown period."

    def __init__(self, retry_after_s: int = 60, **kwargs):
        super().__init__(details={"retry_after_s": retry_after_s}, **kwargs)
        self.retry_after_s = retry_after_s


# ── 502/503/504 Upstream errors ───────────────────────────────────────────────

class UpstreamUnavailableError(ZTError):
    code = "UPSTREAM_UNAVAILABLE"
    status_code = 503
    message = "An upstream dependency is unavailable."


class UpstreamTimeoutError(ZTError):
    code = "UPSTREAM_TIMEOUT"
    status_code = 504
    message = "An upstream dependency timed out."


class SparkNotReadyError(UpstreamUnavailableError):
    message = "Spark session is not yet warm. Please retry shortly."


class S3UnavailableError(UpstreamUnavailableError):
    message = "Object storage is unavailable."


class PostgresUnavailableError(UpstreamUnavailableError):
    message = "Database is unavailable."


class RedisUnavailableError(UpstreamUnavailableError):
    message = "Redis is unavailable."


# ── 500 Internal ───────────────────────────────────────────────────────────────

class InternalError(ZTError):
    code = "INTERNAL"
    status_code = 500
    message = "An internal error occurred."


class AuditFailedError(ZTError):
    code = "AUDIT_FAILED"
    status_code = 500
    message = "Adversarial audit did not pass."
