"""
Database engine and session factories.
Three Postgres databases: zt_app (jobs/locator), zt_rag (vectors), zt_catalog (Iceberg).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.core.config import get_settings

_settings = get_settings()

# ── Engines ──────────────────────────────────────────────────────────────────
_engine_app = create_async_engine(
    _settings.pg_dsn_app,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

_engine_rag = create_async_engine(
    _settings.pg_dsn_rag,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

# ── Session factories ─────────────────────────────────────────────────────────
SessionApp = async_sessionmaker(_engine_app, expire_on_commit=False, class_=AsyncSession)
SessionRag = async_sessionmaker(_engine_rag, expire_on_commit=False, class_=AsyncSession)


class BaseApp(DeclarativeBase):
    pass


class BaseRag(DeclarativeBase):
    pass


@asynccontextmanager
async def get_app_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionApp() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_rag_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionRag() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables() -> None:
    """Create tables in both databases."""
    async with _engine_app.begin() as conn:
        await conn.run_sync(BaseApp.metadata.create_all)
    async with _engine_rag.begin() as conn:
        await conn.run_sync(BaseRag.metadata.create_all)


async def close_engines() -> None:
    await _engine_app.dispose()
    await _engine_rag.dispose()
