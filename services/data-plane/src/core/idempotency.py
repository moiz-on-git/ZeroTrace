"""
Idempotency key middleware — prevents duplicate side effects.
If a request with the same Idempotency-Key is retried, returns the cached response.
Uses Redis for distributed caching (works across multiple instances).
Falls back to in-memory store for single-instance dev.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger("idempotency")
cfg = get_settings()

# In-memory fallback store (single instance only)
_memory_store: dict[str, dict[str, Any]] = {}
MEMORY_TTL_SECONDS = 3600  # 1 hour


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Enforces idempotency on POST/PUT requests with an Idempotency-Key header.
    If the key was seen before (within TTL), returns the cached response.
    """

    def __init__(self, app, ttl_seconds: int = MEMORY_TTL_SECONDS):
        super().__init__(app)
        self.ttl_seconds = ttl_seconds

    async def dispatch(self, request: Request, call_next):
        # Only enforce on mutating methods
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            # No idempotency key — proceed normally
            return await call_next(request)

        # Build a cache key from method + path + idempotency key
        cache_key = self._build_cache_key(request, idempotency_key)

        # Check cache
        cached = await self._get_cached(cache_key)
        if cached is not None:
            # Return cached response
            return Response(
                content=cached["body"],
                status_code=cached["status_code"],
                headers={**cached["headers"], "X-Idempotent-Replay": "true"},
                media_type=cached.get("media_type"),
            )

        # Process the request
        response = await call_next(request)

        # Cache the response if it was successful
        if 200 <= response.status_code < 400:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            await self._set_cached(cache_key, {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": body.decode("utf-8", errors="replace"),
                "media_type": response.media_type,
            })

            # Return a new response with the captured body
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        return response

    def _build_cache_key(self, request: Request, idempotency_key: str) -> str:
        raw = f"{request.method}:{request.url.path}:{idempotency_key}"
        return "zt:idem:" + hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def _get_cached(self, key: str) -> Optional[dict[str, Any]]:
        # Try Redis first
        try:
            from src.core.redis_client import get_async_queue
            r = get_async_queue()
            val = await r.get(key)
            if val:
                return json.loads(val)
        except Exception:
            pass

        # Fall back to in-memory
        entry = _memory_store.get(key)
        if entry and time.time() - entry["ts"] < self.ttl_seconds:
            return entry["data"]
        elif entry:
            _memory_store.pop(key, None)
        return None

    async def _set_cached(self, key: str, data: dict[str, Any]) -> None:
        # Try Redis first
        try:
            from src.core.redis_client import get_async_queue
            r = get_async_queue()
            await r.setex(key, self.ttl_seconds, json.dumps(data))
            return
        except Exception:
            pass

        # Fall back to in-memory
        _memory_store[key] = {"data": data, "ts": time.time()}

        # Cleanup old entries
        now = time.time()
        stale = [k for k, v in _memory_store.items() if now - v["ts"] > self.ttl_seconds]
        for k in stale:
            _memory_store.pop(k, None)
