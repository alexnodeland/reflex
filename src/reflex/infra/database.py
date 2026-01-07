"""Async database configuration with connection pooling.

This module provides the async SQLAlchemy engine and session factory,
plus a raw asyncpg pool for LISTEN/NOTIFY operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from reflex.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# SQLAlchemy async engine with connection pooling
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,  # Validate connections before use
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_pool_max_overflow,
    echo=settings.environment == "development",
)

# Session factory with expire_on_commit=False to prevent implicit I/O
SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Critical for async - prevents implicit I/O after commit
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI routes.

    Yields an async session that is automatically closed after use.
    """
    async with SessionFactory() as session:
        yield session


async def create_raw_pool() -> asyncpg.Pool:
    """Create raw asyncpg pool for LISTEN/NOTIFY.

    SQLAlchemy doesn't expose LISTEN/NOTIFY, so we need a raw pool.
    The pool uses the same connection settings as the SQLAlchemy engine.
    """
    # Convert SQLAlchemy URL to asyncpg format
    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(url)
    # create_pool returns Pool, assertion for type narrowing
    assert pool is not None, "Failed to create asyncpg connection pool"
    return pool


async def init_database() -> None:
    """Initialize database tables.

    Creates all tables defined in SQLModel metadata.
    Should be called once at application startup.
    """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def dispose_engine() -> None:
    """Dispose of the database engine.

    Should be called during application shutdown.
    """
    await engine.dispose()
