"""Health check endpoints for Kubernetes probes.

Provides liveness and readiness endpoints for container orchestration.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Response model for health endpoints."""

    status: str


class ReadyResponse(BaseModel):
    """Response model for readiness endpoint."""

    status: str
    database: str


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
