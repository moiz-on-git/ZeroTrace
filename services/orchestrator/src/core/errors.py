"""
ZeroTrace Exception Hierarchy and Global Error Handlers.
Translates all errors into the standard JSON response envelope.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from core.ulid import generate_ulid
from core.logging import logger


class ZeroTraceException(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code


class ValidationError(ZeroTraceException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("VALIDATION_ERROR", message, details, status.HTTP_422_UNPROCESSABLE_ENTITY)


class UnauthorizedError(ZeroTraceException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__("UNAUTHORIZED", message, None, status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(ZeroTraceException):
    def __init__(self, message: str = "Access forbidden"):
        super().__init__("FORBIDDEN", message, None, status.HTTP_403_FORBIDDEN)


class NotFoundError(ZeroTraceException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__("NOT_FOUND", message, None, status.HTTP_404_NOT_FOUND)


class ConflictError(ZeroTraceException):
    def __init__(self, message: str):
        super().__init__("CONFLICT", message, None, status.HTTP_409_CONFLICT)


class UpstreamUnavailableError(ZeroTraceException):
    def __init__(self, upstream_name: str, message: Optional[str] = None):
        msg = message or f"Upstream service '{upstream_name}' unavailable"
        super().__init__("UPSTREAM_UNAVAILABLE", msg, {"upstream": upstream_name}, status.HTTP_503_SERVICE_UNAVAILABLE)


class AuditFailedError(ZeroTraceException):
    def __init__(self, message: str, residuals: Optional[Any] = None):
        super().__init__("AUDIT_FAILED", message, {"residuals": residuals}, status.HTTP_412_PRECONDITION_FAILED)


class PolicyBlockedError(ZeroTraceException):
    def __init__(self, message: str, citation: Optional[str] = None):
        super().__init__("POLICY_BLOCKED", message, {"citation": citation}, status.HTTP_423_LOCKED)


def build_error_response(code: str, message: str, details: Optional[Dict[str, Any]] = None, status_code: int = 400, req_id: Optional[str] = None) -> JSONResponse:
    request_id = req_id or generate_ulid("req_")
    return JSONResponse(
        status_code=status_code,
        content={
            "data": None,
            "error": {
                "code": code,
                "message": message,
                "details": details or {}
            },
            "request_id": request_id
        }
    )


async def zerotrace_exception_handler(request: Request, exc: ZeroTraceException) -> JSONResponse:
    req_id = getattr(request.state, "request_id", generate_ulid("req_"))
    logger.warn("zerotrace_error_handled", code=exc.code, message=exc.message, request_id=req_id)
    return build_error_response(exc.code, exc.message, exc.details, exc.status_code, req_id)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    req_id = getattr(request.state, "request_id", generate_ulid("req_"))
    errors = exc.errors()
    msg = errors[0].get("msg", "Validation error") if errors else "Invalid request data"
    return build_error_response("VALIDATION_ERROR", msg, {"validation_errors": errors}, status.HTTP_422_UNPROCESSABLE_ENTITY, req_id)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    req_id = getattr(request.state, "request_id", generate_ulid("req_"))
    logger.error("internal_unhandled_error", error=str(exc), request_id=req_id, exc_info=True)
    return build_error_response("INTERNAL", "An internal error occurred", {}, status.HTTP_500_INTERNAL_SERVER_ERROR, req_id)
