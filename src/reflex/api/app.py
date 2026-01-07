"""FastAPI application with lifespan management.

This module creates and configures the FastAPI application with:
- Lifespan handler for startup/shutdown
- Route registration
- Observability instrumentation
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI

from reflex.api.routes import events, health, ws
from reflex.config import settings
from reflex.infra.database import SessionFactory, create_raw_pool, engine
from reflex.infra.locks import ScopedLocks
from reflex.infra.observability import configure_observability, instrument_app
from reflex.infra.store import EventStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle.

    Startup sequence:
    1. Configure observability (Logfire)
    2. Create raw asyncpg pool for LISTEN/NOTIFY
    3. Create httpx.AsyncClient
    4. Create EventStore
    5. Create ScopedLocks
    6. Start agent loop as background task

    Shutdown sequence:
    1. Cancel agent loop (wait for completion)
    2. Close httpx client
    3. Close raw pool
    4. Dispose engine

    Args:
        app: The FastAPI application

    Yields:
        Nothing - just manages lifecycle
    """
    logger.info("Starting application...")

    # 1. Configure observability
    configure_observability()

    # 2. Create raw pool for LISTEN/NOTIFY
    pool = await create_raw_pool()

    # 3. Create HTTP client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )

    # 4. Create EventStore
    store = EventStore(pool=pool, session_factory=SessionFactory)

    # 5. Create ScopedLocks
    locks = ScopedLocks()

    # Store in app.state for access in routes
    app.state.engine = engine
    app.state.session_factory = SessionFactory
    app.state.pool = pool
    app.state.http = http_client
    app.state.store = store
    app.state.locks = locks

    # 6. Start agent loop as background task (optional - can be disabled)
    agent_task: asyncio.Task[None] | None = None
    if settings.environment != "test":
        from reflex.agent.loop import run_loop

        agent_task = asyncio.create_task(run_loop(store))
        logger.info("Agent loop started")

    # Instrument the app with observability
    instrument_app(app)

    logger.info("Application started successfully")

    try:
        yield
    finally:
        logger.info("Shutting down application...")

        # 1. Cancel agent loop
        if agent_task is not None:
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                pass
            logger.info("Agent loop stopped")

        # 2. Close HTTP client
        await http_client.aclose()
        logger.info("HTTP client closed")

        # 3. Close raw pool
        await pool.close()
        logger.info("Database pool closed")

        # 4. Dispose engine
        await engine.dispose()
        logger.info("Database engine disposed")

        logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="Reflex",
        description="Real-time AI Agent Event Processing System",
        version=settings.version,
        lifespan=lifespan,
    )

    # Register routers
    app.include_router(health.router)
    app.include_router(events.router)
    app.include_router(ws.router)

    return app


# Application instance
app = create_app()
