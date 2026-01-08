"""Exception handlers for the FastAPI application.

Provides centralized exception handling for Reflex-specific errors,
converting them to structured JSON responses.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

from reflex.core.errors import ReflexError  # noqa: TC001 - Runtime annotation

if TYPE_CHECKING:
    from fastapi import Request

logger = logging.getLogger(__name__)


async def reflex_exception_handler(
    request: Request,
    exc: ReflexError,
) -> JSONResponse:
    """Handle ReflexError exceptions.

    Converts ReflexError exceptions to structured JSON responses
    with appropriate status codes.

    Args:
        request: The incoming request
        exc: The ReflexError exception

    Returns:
        JSONResponse with structured error body
    """
    # Log the error with context
    logger.warning(
        "Request failed: %s %s - %s: %s",
        request.method,
        request.url.path,
        exc.code.value,
        exc.message,
        extra={
            "error_code": exc.code.value,
            "status_code": exc.status_code,
            "details": exc.details,
        },
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response(),
    )
