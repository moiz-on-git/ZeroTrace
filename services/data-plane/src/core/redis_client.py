"""
Redis connection pools for db0 (semantic cache) and db1 (event bus / ARQ).
"""
from __future__ import annotations

import redis.asyncio as aioredis
import redis as syncredis

from src.core.config import get_settings

_settings = get_settings()

# Async clients
_async_cache_client: aioredis.Redis | None = None
_async_queue_client: aioredis.Redis | None = None

# Sync clients (for seed / reset scripts)
_sync_cache_client: syncredis.Redis | None = None


def get_async_cache() -> aioredis.Redis:
    global _async_cache_client
    if _async_cache_client is None:
        _async_cache_client = aioredis.Redis(
            host=_settings.redis_host,
            port=_settings.redis_port,
            db=_settings.redis_cache_db,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
    return _async_cache_client


def get_async_queue() -> aioredis.Redis:
    global _async_queue_client
    if _async_queue_client is None:
        _async_queue_client = aioredis.Redis(
            host=_settings.redis_host,
            port=_settings.redis_port,
            db=_settings.redis_queue_db,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
    return _async_queue_client


def get_sync_cache() -> syncredis.Redis:
    global _sync_cache_client
    if _sync_cache_client is None:
        _sync_cache_client = syncredis.Redis(
            host=_settings.redis_host,
            port=_settings.redis_port,
            db=_settings.redis_cache_db,
            decode_responses=True,
            socket_timeout=10,
        )
    return _sync_cache_client


async def redis_is_healthy() -> bool:
    try:
        r = get_async_cache()
        await r.ping()
        return True
    except Exception:
        return False
