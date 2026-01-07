"""Pytest configuration and fixtures."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from reflex.core.deps import ReflexDeps
    from reflex.infra.store import EventStore


@pytest.fixture
def anyio_backend() -> str:
    """Configure anyio to use asyncio backend."""
    return "asyncio"


# --- Mock Fixtures (for unit tests without database) ---


@pytest.fixture
def mock_store() -> AsyncMock:
    """Create a mock EventStore for unit tests."""
    store = AsyncMock()
    store.publish = AsyncMock()
    store.subscribe = AsyncMock()
    store.ack = AsyncMock()
    store.nack = AsyncMock()
    store.replay = AsyncMock()
    store.dlq_list = AsyncMock(return_value=[])
    store.dlq_retry = AsyncMock(return_value=True)
    return store


@pytest.fixture
def mock_http() -> MagicMock:
    """Create a mock HTTP client for unit tests."""
    return MagicMock()


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock database session for unit tests."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_deps(mock_store: AsyncMock, mock_http: MagicMock, mock_db: AsyncMock) -> ReflexDeps:
    """Create mock ReflexDeps for unit tests."""
    from reflex.core.deps import ReflexDeps

    return ReflexDeps(
        store=mock_store,
        http=mock_http,
        db=mock_db,
        scope="test",
    )


# --- Integration Fixtures (for tests with real database) ---


def _has_database() -> bool:
    """Check if a real database is available."""
    db_url = os.environ.get("DATABASE_URL", "")
    return "postgresql" in db_url


@pytest.fixture
async def db_pool() -> AsyncIterator[object]:
    """Create asyncpg pool for integration tests.

    Skips if DATABASE_URL is not set (not running in CI).
    """
    if not _has_database():
        pytest.skip("DATABASE_URL not set - skipping integration test")

    import asyncpg

    from reflex.config import settings

    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(url)
    assert pool is not None

    yield pool

    await pool.close()


@pytest.fixture
async def db_engine() -> AsyncIterator[object]:
    """Create SQLAlchemy engine for integration tests.

    Skips if DATABASE_URL is not set.
    """
    if not _has_database():
        pytest.skip("DATABASE_URL not set - skipping integration test")

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlmodel import SQLModel

    from reflex.config import settings

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    # Drop tables after test
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine: object) -> object:
    """Create session factory for integration tests."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession

    return async_sessionmaker(
        db_engine,  # type: ignore[arg-type]
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
async def store(db_pool: object, session_factory: object) -> AsyncIterator[EventStore]:
    """Create EventStore for integration tests."""
    from reflex.infra.store import EventStore

    store = EventStore(
        pool=db_pool,  # type: ignore[arg-type]
        session_factory=session_factory,  # type: ignore[arg-type]
    )
    yield store


@pytest.fixture
async def real_deps(store: EventStore) -> AsyncIterator[ReflexDeps]:
    """Create real ReflexDeps for integration tests."""
    import httpx

    from reflex.core.deps import ReflexDeps

    async with httpx.AsyncClient() as http:
        # Create a mock db session since we don't need it for most tests
        db = AsyncMock()
        yield ReflexDeps(
            store=store,
            http=http,
            db=db,
            scope="integration-test",
        )


# --- API Test Fixtures ---


@pytest.fixture
def test_app(mock_store: AsyncMock) -> FastAPI:
    """Create a test FastAPI app with mocked dependencies."""
    from reflex.api.routes import events, health

    app = FastAPI()
    app.include_router(health.router)
    app.include_router(events.router)

    # Set up app state with mocked dependencies
    app.state.store = mock_store
    mock_session_factory = MagicMock()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=1)))
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)
    app.state.session_factory = mock_session_factory

    return app


@pytest.fixture
def test_client(test_app: FastAPI) -> Iterator[TestClient]:
    """Create a test client."""
    with TestClient(test_app) as client:
        yield client
