"""
Liveness and readiness endpoints for Kubernetes-style orchestration.
- /live  : is the process alive?
- /ready : are all dependencies ready to serve traffic?
- /metrics: Prometheus metrics
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, JSONResponse

from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.metrics import metrics
from src.core.redis_client import redis_is_healthy
from src.core.s3_client import bucket_is_healthy
from src.core.spark_session import is_spark_warm

router = APIRouter()
logger = get_logger("lifecycle")
_start_time = time.time()
_ready: bool = False

cfg = get_settings()


def set_ready(value: bool) -> None:
    global _ready
    _ready = value


@router.get("/live")
async def liveness():
    """Liveness probe — process is alive."""
    return {"status": "alive", "uptime_s": round(time.time() - _start_time, 1)}


@router.get("/ready")
async def readiness():
    """Readiness probe — all dependencies are ready to serve."""
    checks: dict[str, Any] = {}

    # Postgres
    try:
        import psycopg
        conn = psycopg.connect(
            f"host={cfg.pg_host} port={cfg.pg_port} dbname={cfg.pg_db_app} "
            f"user={cfg.pg_user} password={cfg.pg_password}",
            connect_timeout=2,
        )
        conn.close()
        checks["postgres"] = "ok"
        metrics.db_connected.set(1)
    except Exception as e:
        checks["postgres"] = f"down: {str(e)[:50]}"
        metrics.db_connected.set(0)

    # Redis
    redis_ok = await redis_is_healthy()
    checks["redis"] = "ok" if redis_ok else "down"
    metrics.redis_connected.set(1 if redis_ok else 0)

    # S3
    try:
        s3_ok = bucket_is_healthy()
        checks["s3"] = "ok" if s3_ok else "down"
        metrics.s3_connected.set(1 if s3_ok else 0)
    except Exception:
        checks["s3"] = "down"
        metrics.s3_connected.set(0)

    # Spark
    spark_ok = is_spark_warm()
    checks["spark_warm"] = "ok" if spark_ok else "warming"
    metrics.spark_warm.set(1 if spark_ok else 0)

    # Overall
    all_ready = all(
        v == "ok" or (k == "spark_warm" and v in ("ok", "warming"))
        for k, v in checks.items()
    )
    set_ready(all_ready)

    status_code = 200 if all_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "ready": all_ready,
            "checks": checks,
            "uptime_s": round(time.time() - _start_time, 1),
        },
    )


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus text exposition format metrics."""
    return PlainTextResponse(
        content=metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
