"""Health check endpoints for Kubernetes probes.

Provides liveness, readiness, and detailed health endpoints for
container orchestration and monitoring.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

if TYPE_CHECKING:
    from fastapi import FastAPI

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Response model for health endpoints."""

    status: str


class ReadyResponse(BaseModel):
    """Response model for readiness endpoint."""

    status: str
    database: str


@dataclass
class HealthIndicator:
    """Health indicator for a specific component.

    Attributes:
        name: Component name (e.g., "database", "event_queue")
        status: Health status
        message: Optional status message or error details
        latency_ms: Optional latency in milliseconds
    """

    name: str
    status: Literal["healthy", "degraded", "unhealthy"]
    message: str | None = None
    latency_ms: float | None = None


async def check_database(app: FastAPI) -> HealthIndicator:
    """Check database connectivity.

    Args:
        app: The FastAPI application

    Returns:
        HealthIndicator with database status
    """
    start = time.monotonic()
    try:
        async with app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
        latency = (time.monotonic() - start) * 1000
        return HealthIndicator("database", "healthy", latency_ms=latency)
    except Exception as e:
        return HealthIndicator("database", "unhealthy", str(e))


async def check_event_queue(app: FastAPI) -> HealthIndicator:
    """Check event queue depth.

    Args:
        app: The FastAPI application

    Returns:
        HealthIndicator with queue status (degraded if > 10000 pending)
    """
    try:
        async with app.state.session_factory() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM events WHERE status = 'pending'")
            )
            pending = result.scalar() or 0

        if pending > 10000:
            return HealthIndicator("event_queue", "degraded", f"{pending} pending events")
        return HealthIndicator("event_queue", "healthy", f"{pending} pending")
    except Exception as e:
        return HealthIndicator("event_queue", "unhealthy", str(e))


async def check_dlq(app: FastAPI) -> HealthIndicator:
    """Check dead-letter queue size.

    Args:
        app: The FastAPI application

    Returns:
        HealthIndicator with DLQ status (degraded if > 100 events)
    """
    try:
        async with app.state.session_factory() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM events WHERE status = 'dlq'"))
            dlq_count = result.scalar() or 0

        if dlq_count > 100:
            return HealthIndicator("dlq", "degraded", f"{dlq_count} events in DLQ")
        return HealthIndicator("dlq", "healthy", f"{dlq_count} in DLQ")
    except Exception as e:
        return HealthIndicator("dlq", "unhealthy", str(e))


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Returns healthy if the process is running. Used by Kubernetes liveness probes.",
)
async def health() -> HealthResponse:
    """Check if the service is alive.

    This endpoint always returns 200 if the process is running.
    It does not check external dependencies.

    Returns:
        Health status
    """
    return HealthResponse(status="healthy")


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe",
    description="Returns ready if the service can accept traffic. Checks database connectivity.",
    responses={
        200: {"description": "Service is ready"},
        503: {"description": "Service is not ready"},
    },
)
async def ready(request: Request) -> JSONResponse:
    """Check if the service is ready to accept traffic.

    Verifies database connectivity before returning ready.
    Returns 503 if any critical dependency is unavailable.

    Args:
        request: The current request

    Returns:
        Readiness status with component health
    """
    db_status = "unknown"

    try:
        # Check database connectivity
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception:
        db_status = "disconnected"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "database": db_status},
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ready", "database": db_status},
    )


class DetailedHealthResponse(BaseModel):
    """Response model for detailed health endpoint."""

    status: Literal["healthy", "degraded", "unhealthy"]
    indicators: list[dict[str, Any]]


@router.get(
    "/health/detailed",
    response_model=DetailedHealthResponse,
    summary="Detailed health check",
    description="Returns comprehensive health status with all component indicators.",
    responses={
        200: {"description": "Health check completed"},
    },
)
async def detailed_health(request: Request) -> dict[str, Any]:
    """Detailed health check with all indicators.

    Checks multiple components concurrently:
    - Database connectivity and latency
    - Event queue depth (degraded if > 10000 pending)
    - Dead-letter queue size (degraded if > 100 events)

    Args:
        request: The current request

    Returns:
        Overall status and individual component indicators
    """
    app = request.app
    indicators = await asyncio.gather(
        check_database(app),
        check_event_queue(app),
        check_dlq(app),
    )

    # Determine overall status (unhealthy > degraded > healthy)
    overall: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    for ind in indicators:
        if ind.status == "unhealthy":
            overall = "unhealthy"
            break
        if ind.status == "degraded":
            overall = "degraded"

    return {
        "status": overall,
        "indicators": [asdict(ind) for ind in indicators],
    }
