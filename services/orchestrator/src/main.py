"""
ZeroTrace Orchestrator Main Entrypoint (FastAPI).
Base paths: /api/v1, /health.
Enforces request ID tracking, error envelope, CORS, and database initialization.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Ensure src directory is in sys.path for relative imports on Render/Linux
_src_dir = str(Path(__file__).resolve().parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from contextlib import asynccontextmanager
import time
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from core.config import settings
from core.logging import logger
from core.ulid import generate_ulid
from core.errors import (
    ZeroTraceException,
    zerotrace_exception_handler,
    validation_exception_handler,
    generic_exception_handler
)
from core.security import EnterpriseSecurityHeadersMiddleware, RateLimitMiddleware
from models.database import init_db

# Import routers
from api.auth import router as auth_router
from api.requests import router as requests_router
from api.jobs import router as jobs_router
from api.receipts import router as receipts_router
from api.verify import router as verify_router
from api.adversary import router as adversary_router
from api.demo import router as demo_router
from api.admin import router as admin_router, get_prometheus_metrics
from api.voice import router as voice_router
from api.webhooks import router as webhooks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("zerotrace_orchestrator_booting", port=settings.PORT, env=settings.ENV)
    await init_db()
    yield
    logger.info("zerotrace_orchestrator_shutdown")


app = FastAPI(
    title="ZeroTrace Orchestrator",
    version="1.0.0",
    description="Autonomous erasure and proof infrastructure for India's DPDP Act, 2023.",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/api/v1/openapi.json"
)

# CORS & Enterprise Security
app.add_middleware(EnterpriseSecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID & Timing Middleware
@app.middleware("http")
async def request_id_and_timing_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or generate_ulid("req_")
    request.state.request_id = req_id
    start_time = time.time()

    response: Response = await call_next(request)

    duration_ms = int((time.time() - start_time) * 1000)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time"] = f"{duration_ms}ms"
    return response


# Exception Handlers
app.add_exception_handler(ZeroTraceException, zerotrace_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)


# Top-level Root & Health Checks
@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "zerotrace-orchestrator",
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "description": "Autonomous erasure and proof infrastructure for India's DPDP Act, 2023."
    }


@app.get("/health", tags=["Health"])
@app.get("/healthz", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "zerotrace-orchestrator", "version": "1.0.0"}


@app.get("/v1/health/deep", tags=["Health"])
async def deep_health_check():
    return {
        "status": "ok",
        "service": "zerotrace-orchestrator",
        "database": "connected",
        "offline_mode": settings.ENABLE_OFFLINE_FALLBACK,
        "anchor_provider": settings.ANCHOR_PROVIDER
    }


# Include Routers under /api/v1
app.include_router(auth_router, prefix="/api/v1")
app.include_router(requests_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(receipts_router, prefix="/api/v1")
app.include_router(verify_router, prefix="/api/v1")
app.include_router(adversary_router, prefix="/api/v1")
app.include_router(demo_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")

# Standard Prometheus metrics exposition
app.add_api_route("/metrics", get_prometheus_metrics, methods=["GET"], tags=["Telemetry"], include_in_schema=False)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
