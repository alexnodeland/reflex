"""FastAPI application with lifespan management.

This module creates and configures the FastAPI application with:
- Lifespan handler for startup/shutdown
- Route registration
- Observability instrumentation
- Rate limiting middleware
- Task supervision for background tasks
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
from slowapi.errors import RateLimitExceeded

from reflex.api.rate_limiting import limiter, rate_limit_exceeded_handler
from reflex.api.routes import events, health, ws
from reflex.config import settings
from reflex.infra.database import SessionFactory, create_raw_pool, engine
from reflex.infra.locks import ScopedLocks, create_lock_backend
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

    # 5. Create ScopedLocks with configurable backend
    # Use "postgres" for distributed deployments (Kubernetes, multi-replica)
    # Use "memory" for single-process deployments (default, with warning)
    lock_backend = create_lock_backend(
        settings.lock_backend,
        pool=pool,
        warn_on_memory=(settings.environment != "test"),
    )
    locks = ScopedLocks(lock_backend)
    logger.info("Lock backend: %s", settings.lock_backend)

    # Store in app.state for access in routes
    app.state.engine = engine
    app.state.session_factory = SessionFactory
    app.state.pool = pool
    app.state.http = http_client
    app.state.store = store
    app.state.locks = locks

    # 6. Start agent loop as background task with supervision (optional - can be disabled)
    shutdown_event = asyncio.Event()
    supervisor_task: asyncio.Task[None] | None = None
    if settings.environment != "test":
        from reflex.agent.loop import run_loop

        async def supervised_agent_loop() -> None:
            """Run agent loop with automatic restart on failure."""
            restart_delay = 1.0
            max_restart_delay = 60.0

            while not shutdown_event.is_set():
                try:
                    logger.info("Starting agent loop...")
                    await run_loop(store)
                except asyncio.CancelledError:
                    logger.info("Agent loop cancelled")
                    break
                except Exception:
                    logger.exception("Agent loop crashed, restarting in %.1fs", restart_delay)
                    try:
                        await asyncio.wait_for(shutdown_event.wait(), timeout=restart_delay)
                        break  # Shutdown requested during delay
                    except TimeoutError:
                        pass  # Timeout expired, restart
                    # Exponential backoff for restarts
                    restart_delay = min(restart_delay * 2, max_restart_delay)

        supervisor_task = asyncio.create_task(supervised_agent_loop())
        logger.info("Agent supervisor started")

    # Instrument the app with observability
    instrument_app(app)

    logger.info("Application started successfully")

    try:
        yield
    finally:
        logger.info("Shutting down application...")

        # 1. Signal shutdown and cancel supervisor
        shutdown_event.set()
        if supervisor_task is not None:
            supervisor_task.cancel()
            try:
                await supervisor_task
            except asyncio.CancelledError:
                pass
            logger.info("Agent supervisor stopped")

        # 2. Close lock backend
        await lock_backend.close()
        logger.info("Lock backend closed")

        # 3. Close HTTP client
        await http_client.aclose()
        logger.info("HTTP client closed")

        # 4. Close raw pool
        await pool.close()
        logger.info("Database pool closed")

        # 5. Dispose engine
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

    # Add rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # Register routers
    app.include_router(health.router)
    app.include_router(events.router)
    app.include_router(ws.router)

    return app


# Application instance
app = create_app()
