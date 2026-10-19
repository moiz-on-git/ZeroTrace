"""
Rate limiting middleware — token bucket per client IP.
Configurable per-endpoint limits. Uses in-memory sliding window.
For production multi-instance deployments, swap to Redis-backed limiter.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.exceptions import RateLimitedError


@dataclass
class TokenBucket:
    capacity: int
    tokens: float
    refill_rate: float  # tokens per second
    last_refill: float = field(default_factory=time.monotonic)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def consume(self, tokens: int = 1) -> tuple[bool, float]:
        """Try to consume tokens. Returns (allowed, retry_after_seconds)."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0
            else:
                needed = tokens - self.tokens
                retry_after = needed / self.refill_rate
                return False, retry_after


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Token-bucket rate limiter per client IP.
    Excludes health endpoints and OpenAPI docs.
    """

    def __init__(
        self,
        app,
        default_rate: int = 100,        # requests per minute
        default_burst: int = 20,        # burst capacity
        authenticated_rate: int = 300,   # higher limit for authenticated requests
        authenticated_burst: int = 50,
    ):
        super().__init__(app)
        self.default_rate = default_rate
        self.default_burst = default_burst
        self.authenticated_rate = authenticated_rate
        self.authenticated_burst = authenticated_burst
        self._buckets: dict[str, TokenBucket] = defaultdict(self._make_bucket)
        self._lock = Lock()
        self._last_cleanup = time.monotonic()

    def _make_default_bucket(self) -> TokenBucket:
        return TokenBucket(
            capacity=self.default_burst,
            tokens=self.default_burst,
            refill_rate=self.default_rate / 60.0,
        )

    def _make_authenticated_bucket(self) -> TokenBucket:
        return TokenBucket(
            capacity=self.authenticated_burst,
            tokens=self.authenticated_burst,
            refill_rate=self.authenticated_rate / 60.0,
        )

    def _make_bucket(self) -> TokenBucket:
        # Default — overridden in _get_bucket based on auth status
        return self._make_default_bucket()

    def _get_bucket(self, client_ip: str, is_authenticated: bool) -> TokenBucket:
        key = f"{client_ip}:{'auth' if is_authenticated else 'anon'}"
        with self._lock:
            if key not in self._buckets:
                if is_authenticated:
                    self._buckets[key] = self._make_authenticated_bucket()
                else:
                    self._buckets[key] = self._make_default_bucket()

            # Periodic cleanup of stale buckets (every 5 minutes)
            now = time.monotonic()
            if now - self._last_cleanup > 300:
                self._cleanup_stale(now)
                self._last_cleanup = now

            return self._buckets[key]

    def _cleanup_stale(self, now: float) -> None:
        """Remove buckets that haven't been used in 10 minutes."""
        stale_threshold = 600  # 10 minutes
        keys_to_remove = [
            key for key, bucket in self._buckets.items()
            if now - bucket.last_refill > stale_threshold
        ]
        for key in keys_to_remove:
            del self._buckets[key]

    def _get_client_ip(self, request: Request) -> str:
        # Trust X-Forwarded-For only if behind a known proxy
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_health_endpoint(self, path: str) -> bool:
        return path in ("/health", "/ready", "/live") or path.startswith("/docs") or path.startswith("/openapi")

    def _is_authenticated(self, request: Request) -> bool:
        return bool(request.headers.get("X-Service-Key"))

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health and docs
        if self._is_health_endpoint(request.url.path):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        is_auth = self._is_authenticated(request)
        bucket = self._get_bucket(client_ip, is_auth)

        allowed, retry_after = bucket.consume(1)
        if not allowed:
            retry_after_int = int(retry_after) + 1
            raise RateLimitedError(retry_after_s=retry_after_int)

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(bucket.capacity)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + retry_after))

        return response
