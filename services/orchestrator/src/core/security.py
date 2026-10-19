"""
ZeroTrace Enterprise Security Middleware & Rate Limiting.
Enforces:
1. Strict OWASP / RBI Cyber Security Framework HTTP security headers.
2. In-memory sliding-window rate limiting per client IP to prevent denial-of-service / resource exhaustion.
"""

from __future__ import annotations
import time
from typing import Dict, List, Tuple
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from core.errors import build_error_response
from core.config import settings


class EnterpriseSecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        # OWASP & Banking Grade Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(self), camera=()"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response


class RateLimiter:
    """
    Sliding window in-memory rate limiter per IP address.
    """
    def __init__(self, max_requests: int = 120, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = {}

    def is_allowed(self, client_ip: str) -> Tuple[bool, int]:
        now = time.time()
        window_start = now - self.window_seconds

        timestamps = self._history.get(client_ip, [])
        # Prune older than window
        timestamps = [t for t in timestamps if t > window_start]

        if len(timestamps) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - timestamps[0]))
            self._history[client_ip] = timestamps
            return False, max(1, retry_after)

        timestamps.append(now)
        self._history[client_ip] = timestamps
        return True, 0

    def get_remaining(self, client_ip: str) -> int:
        now = time.time()
        window_start = now - self.window_seconds
        timestamps = [t for t in self._history.get(client_ip, []) if t > window_start]
        return max(0, self.max_requests - len(timestamps))

    def reset_client(self, client_ip: str) -> None:
        self._history.pop(client_ip, None)


# Default rate limiter: 180 req/min
global_rate_limiter = RateLimiter(max_requests=180, window_seconds=60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Whitelist health checks, metrics, and documentation from rate limiting
        path = request.url.path
        if path in ("/health", "/v1/health/deep", "/metrics", "/docs", "/api/v1/openapi.json"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        allowed, retry_after = global_rate_limiter.is_allowed(client_ip)

        if not allowed:
            res = build_error_response(
                code="RATE_LIMIT_EXCEEDED",
                message=f"Rate limit exceeded. Please retry after {retry_after} seconds.",
                details={"retry_after_seconds": retry_after},
                status_code=429
            )
            res.headers["Retry-After"] = str(retry_after)
            res.headers["X-RateLimit-Limit"] = str(global_rate_limiter.max_requests)
            res.headers["X-RateLimit-Remaining"] = "0"
            return res

        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(global_rate_limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(global_rate_limiter.get_remaining(client_ip))
        return response
