"""
ZeroTrace Data Plane — FastAPI application entry point (production-grade).

Startup sequence:
  1. Configure structured logging with PII redaction
  2. Create DB tables / run migrations
  3. Ensure S3 bucket exists with versioning
  4. Start Spark session (long-lived, pre-warmed) in background
  5. Register all middleware (rate limiting, idempotency, security, metrics)
  6. Serve API

Shutdown sequence:
  1. Signal graceful shutdown — reject new requests with 503
  2. Stop accepting new background tasks
  3. Drain in-flight requests
  4. Stop Spark, close DB/Redis connections
"""
from __future__ import annotations

import asyncio
import signal
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager

# ── Windows async event loop fix for psycopg/asyncpg ─────────────────────────
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass  # Python 3.16+ deprecation — silently ignore

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import audit, demo, erasure, health, inventory, locate
from src.core.config import get_settings
from src.core.db import create_all_tables, close_engines
from src.core.exceptions import ZTError
from src.core.lifecycle import router as lifecycle_router
from src.core.logging import configure_logging, get_logger
from src.core.middleware import (
    CorrelationIdMiddleware,
    GracefulShutdownMiddleware,
    MetricsMiddleware,
    RequestSizeLimitMiddleware,
    RequestTimeoutMiddleware,
    SecurityHeadersMiddleware,
)
from src.core.rate_limiter import RateLimiterMiddleware
from src.core.idempotency import IdempotencyMiddleware
from src.core.s3_client import ensure_bucket_exists
from src.core.spark_session import init_spark, stop_spark

cfg = get_settings()
configure_logging(cfg.log_level)
logger = get_logger("main")


# ── Lifecycle ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("startup.begin", env=cfg.env, port=cfg.data_plane_port)

    # Register signal handlers for graceful shutdown
    def _signal_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info("shutdown.signal_received", signal=sig_name)
        GracefulShutdownMiddleware.begin_shutdown()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _signal_handler)
        except (ValueError, OSError):
            pass  # Not in main thread during tests

    # Create DB tables
    try:
        await create_all_tables()
        logger.info("startup.db_tables_ready")
    except Exception as e:
        logger.error("startup.db_tables_failed", error=str(e))

    # Ensure S3 bucket
    try:
        ensure_bucket_exists(versioning=cfg.s3_versioning_enabled)
        logger.info("startup.s3_bucket_ready", bucket=cfg.s3_bucket)
    except Exception as e:
        logger.warning("startup.s3_bucket_failed", error=str(e))

    # Start Spark in background thread so it doesn't block health endpoints
    def _spark_init():
        try:
            init_spark()
            logger.info("startup.spark_warm")
        except Exception as exc:
            logger.error("startup.spark_failed", error=str(exc))

    t = threading.Thread(target=_spark_init, daemon=True, name="spark-init")
    t.start()
    logger.info("startup.spark_initialising_in_background")

    # Pre-warm the embedding model in background (avoid first-request latency)
    def _embed_warmup():
        try:
            from src.seed.vector_seeder import get_embedding_model
            get_embedding_model()
            logger.info("startup.embed_model_warm")
        except Exception as exc:
            logger.warning("startup.embed_model_warmup_failed", error=str(exc))

    t2 = threading.Thread(target=_embed_warmup, daemon=True, name="embed-warmup")
    t2.start()

    logger.info("startup.complete")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("shutdown.begin")
    GracefulShutdownMiddleware.begin_shutdown()

    # Give in-flight requests a moment to drain
    await asyncio.sleep(0.5)

    # Close connections
    stop_spark()
    await close_engines()
    logger.info("shutdown.complete")


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ZeroTrace Data Plane",
    description=(
        "Simulated Kaveri Finserv NBFC data stack + erasure engine + adversarial audit. "
        "Part of ZeroTrace — DPDP Act erasure infrastructure. "
        'Positioning: "Stripe for Data Destruction."'
    ),
    version="1.0.0",
    docs_url="/docs" if cfg.env != "production" else None,
    redoc_url="/redoc" if cfg.env != "production" else None,
    openapi_url="/openapi.json" if cfg.env != "production" else None,
    lifespan=lifespan,
)

# ── Middleware Stack (order matters — outermost first) ────────────────────────
# The first add_middleware call is the outermost layer (runs first on request,
# last on response). We add in reverse execution order.

# 7. Graceful shutdown (reject new requests during shutdown)
app.add_middleware(GracefulShutdownMiddleware)

# 6. Security headers
app.add_middleware(SecurityHeadersMiddleware)

# 5. Request size limit (50MB for audio uploads)
app.add_middleware(RequestSizeLimitMiddleware, max_body_bytes=50 * 1024 * 1024)

# 4. Request timeout (120s for long-running erasure operations)
app.add_middleware(RequestTimeoutMiddleware, timeout_seconds=120)

# 3. Metrics collection
app.add_middleware(MetricsMiddleware)

# 2. Idempotency key handling (mutating endpoints only)
app.add_middleware(IdempotencyMiddleware)

# 1. Rate limiting
app.add_middleware(
    RateLimiterMiddleware,
    default_rate=120,        # 120/min anonymous
    default_burst=20,        # burst of 20
    authenticated_rate=600,   # 600/min with service key
    authenticated_burst=100,
)

# 0. CORS (innermost — applied last on response)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8001",
        "https://zerotrace.ai",
        "https://www.zerotrace.ai",
        "https://console.zerotrace.ai",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)

# 0a. Correlation ID (innermost)
app.add_middleware(CorrelationIdMiddleware)


# ── Request ID ──────────────────────────────────────────────────────────────────

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Request Logging ─────────────────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    logger.info(
        "http.request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
        request_id=getattr(request.state, "request_id", ""),
        correlation_id=getattr(request.state, "correlation_id", ""),
    )
    return response


# ── Exception Handlers ──────────────────────────────────────────────────────────

@app.exception_handler(ZTError)
async def zt_error_handler(request: Request, exc: ZTError):
    """Handle all ZeroTrace custom exceptions — structured error envelope."""
    logger.warning(
        "zt_error",
        code=exc.code,
        message=exc.message,
        path=request.url.path,
        request_id=getattr(request.state, "request_id", ""),
    )
    headers = {}
    if exc.code == "RATE_LIMITED":
        headers["Retry-After"] = str(exc.details.get("retry_after_s", 60))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "data": None,
            "error": exc.to_dict(),
            "request_id": getattr(request.state, "request_id", ""),
        },
        headers=headers,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unexpected errors — never leak internals."""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        error=type(exc).__name__,
        error_message=str(exc),
        request_id=getattr(request.state, "request_id", ""),
        correlation_id=getattr(request.state, "correlation_id", ""),
    )
    return JSONResponse(
        status_code=500,
        content={
            "data": None,
            "error": {
                "code": "INTERNAL",
                "message": "An internal error occurred. The team has been notified.",
                "details": {},
            },
            "request_id": getattr(request.state, "request_id", ""),
        },
    )


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(lifecycle_router)   # /live, /ready, /metrics
app.include_router(health.router)       # /health, /v1/health/deep
app.include_router(inventory.router)
app.include_router(locate.router)
app.include_router(erasure.router)
app.include_router(audit.router)
app.include_router(demo.router)


# ── Root endpoint ──────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "ZeroTrace Data Plane",
        "version": "1.0.0",
        "status": "ok",
        "docs": "/docs" if cfg.env != "production" else "disabled",
        "health": "/health",
        "ready": "/ready",
        "metrics": "/metrics",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=cfg.data_plane_port,
        reload=cfg.env == "development",
        log_level=cfg.log_level.lower(),
        workers=1,  # Spark session is not multi-worker safe
        timeout_keep_alive=30,
        timeout_graceful_shutdown=10,
        access_log=False,  # We have our own structured logging
    )
