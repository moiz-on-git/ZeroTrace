# ───────────────────────────────────────────────────────────────────────────────
# ZeroTrace Data Plane — Production Dockerfile
# Multi-stage: builder → embed model → runtime
# Target: ~1.5GB image with Java 17 + Python 3.11 + Spark + embedding model
# ───────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder — install Python dependencies ──────────────────────────
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install deps (cached layer — only rebuilds when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "sqlalchemy[asyncio]" asyncpg greenlet

# ── Stage 2: Embedding model — download at build time ───────────────────────
FROM python:3.11-slim AS embed-builder

RUN pip install --no-cache-dir sentence-transformers

RUN python -c "\
from sentence_transformers import SentenceTransformer; \
m = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2'); \
m.save('/models/embed'); \
print('Embedding model saved')"

# ── Stage 3: Runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# ── System packages: Java 17, curl for healthcheck, tini for signal handling ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PYSPARK_PYTHON=python3
ENV PYSPARK_DRIVER_PYTHON=python3

# ── Non-root user (security) ────────────────────────────────────────────────
RUN groupadd -r ztuser && useradd -r -g ztuser -u 1000 -s /bin/bash ztuser

WORKDIR /app

# ── Copy Python packages from builder (layer caching) ───────────────────────
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# ── Copy embedding model from embed-builder ─────────────────────────────────
COPY --from=embed-builder /models/embed /app/models/embed

# ── Copy application source (changes most frequently — last layer) ─────────
COPY --chown=ztuser:ztuser . /app/

# ── Environment ───────────────────────────────────────────────────────────────
ENV ZT_ENV=production \
    ZT_DATA_PLANE_PORT=8002 \
    ZT_EMBED_MODEL_PATH=/app/models/embed \
    ZT_LOG_LEVEL=INFO \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC

USER ztuser

EXPOSE 8002

# ── Health check: liveness (process alive) ───────────────────────────────────
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8002/live || exit 1

# ── Use tini for proper PID 1 signal handling (graceful shutdown) ──────────────
# Workers=1 because Spark session is not multi-worker safe
# --proxy-headers for when behind Caddy/Nginx
# --timeout-keep-alive=30 to close idle connections
# --timeout-graceful-shutdown=10 to allow in-flight requests to drain
ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "uvicorn", "src.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8002", \
     "--workers", "1", \
     "--log-level", "info", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*", \
     "--timeout-keep-alive", "30", \
     "--timeout-graceful-shutdown", "10", \
     "--access-log"]
