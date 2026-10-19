"""
ZeroTrace Database Engine and Session Factory.
Supports Postgres (production/EC2) and SQLite async (development/offline demo-in-a-box).
"""

from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from core.config import settings
from core.logging import logger
from models.entities import Base

# Engine configuration
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def init_db() -> None:
    """
    Initializes database schema (idempotent — safe to call on every boot).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_schema_initialized", url=settings.DATABASE_URL.split("@")[-1])


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an active database session.
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncIterator[AsyncSession]:
    """
    Async context manager for obtaining a DB session outside of FastAPI DI.
    Use in scripts, workers, tests, and standalone coroutines.

    Usage:
        async with get_db_session() as session:
            result = await session.execute(...)
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
