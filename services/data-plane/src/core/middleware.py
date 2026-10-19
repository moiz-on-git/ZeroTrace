"""
Production middleware: security headers, request timeout, request size limit,
metrics collection, correlation IDs, graceful shutdown flag.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.metrics import metrics


# ── Security Headers ──────────────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        # Prevent API responses from being cached unless explicitly set
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response


# ── Request Timeout ─────────────────────────────────────────────────────────────

class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Aborts requests that exceed the configured timeout."""

    def __init__(self, app, timeout_seconds: int = 120):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next):
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            from src.core.exceptions import UpstreamTimeoutError
            raise UpstreamTimeoutError(
                message=f"Request timed out after {self.timeout_seconds}s",
                details={"path": request.url.path, "method": request.method},
            )


# ── Request Size Limit ────────────────────────────────────────────────────────

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects requests with bodies larger than the configured max."""

    def __init__(self, app, max_body_bytes: int = 50 * 1024 * 1024):  # 50MB default (for audio uploads)
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("Content-Length")
        if content_length and int(content_length) > self.max_body_bytes:
            from src.core.exceptions import ValidationError
            raise ValidationError(
                message=f"Request body exceeds maximum size of {self.max_body_bytes // (1024*1024)}MB",
                details={"max_body_bytes": self.max_body_bytes},
            )
        return await call_next(request)


# ── Metrics Collection ──────────────────────────────────────────────────────────

class MetricsMiddleware(BaseHTTPMiddleware):
    """Records HTTP metrics for every request."""

    async def dispatch(self, request: Request, call_next):
        # Skip health and docs endpoints
        if request.url.path in ("/health", "/live", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        metrics.http_requests_in_flight.inc()

        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration = time.perf_counter() - start

            # Record metrics
            method = request.method
            path = request.url.path
            status = str(response.status_code)

            metrics.http_requests_total.inc(method=method, path=path, status=status)
            metrics.http_request_duration_seconds.observe(
                duration, method=method, path=path
            )

            # Add Server-Timing header
            response.headers["Server-Timing"] = f"total;dur={int(duration * 1000)}"

            return response
        finally:
            metrics.http_requests_in_flight.dec()


# ── Correlation ID ──────────────────────────────────────────────────────────────

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Ensures every request has a correlation ID for tracing."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or f"corr_{uuid.uuid4().hex[:16]}"
        request.state.correlation_id = correlation_id

        # Also set it in structlog context for structured logging
        from structlog.contextvars import bind_contextvars
        bind_contextvars(correlation_id=correlation_id, request_id=correlation_id)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


# ── Graceful Shutdown ──────────────────────────────────────────────────────────

class GracefulShutdownMiddleware(BaseHTTPMiddleware):
    """
    During shutdown, rejects new requests with 503 + Retry-After.
    In-flight requests are allowed to complete.
    """
    _shutting_down: bool = False

    @classmethod
    def begin_shutdown(cls) -> None:
        cls._shutting_down = True

    async def dispatch(self, request: Request, call_next):
        if self._shutting_down:
            return Response(
                content='{"data":null,"error":{"code":"UPSTREAM_UNAVAILABLE","message":"Server is shutting down. Please retry."},"request_id":""}',
                status_code=503,
                headers={"Retry-After": "5", "Content-Type": "application/json"},
            )
        return await call_next(request)
