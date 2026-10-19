"""Health and deep-health endpoints."""
from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api.schemas import ApiResponse, DeepHealthResponse
from src.core.config import get_settings
from src.core.s3_client import bucket_is_healthy
from src.core.redis_client import redis_is_healthy
from src.core.spark_session import is_spark_warm

router = APIRouter()
_start_time = time.time()
cfg = get_settings()


@router.get("/health")
async def health():
    return {"status": "ok", "service": "data-plane"}


@router.get("/v1/health/deep")
async def deep_health():
    import asyncio
    import psycopg

    spark_ok = is_spark_warm()

    # S3
    try:
        s3_ok = bucket_is_healthy()
    except Exception:
        s3_ok = False

    # Postgres
    try:
        pg_dsn = cfg.pg_dsn_app
        conn = await asyncio.to_thread(
            lambda: __import__("psycopg").connect(
                f"host={cfg.pg_host} port={cfg.pg_port} dbname={cfg.pg_db_app} "
                f"user={cfg.pg_user} password={cfg.pg_password}"
            )
        )
        conn.close()
        pg_ok = True
    except Exception:
        pg_ok = False

    # Redis
    redis_ok = await redis_is_healthy()

    status = "ok"
    if not all([spark_ok, s3_ok, pg_ok, redis_ok]):
        status = "degraded"
    if not pg_ok or not redis_ok:
        status = "down"

    resp = DeepHealthResponse(
        status=status,
        spark_warm=spark_ok,
        s3_ok=s3_ok,
        pg_ok=pg_ok,
        redis_ok=redis_ok,
        versions={
            "python": __import__("platform").python_version(),
            "fastapi": __import__("fastapi").__version__,
            "pydantic": __import__("pydantic").version.VERSION,
        },
        uptime_s=round(time.time() - _start_time, 1),
    )

    return ApiResponse(data=resp.model_dump())
