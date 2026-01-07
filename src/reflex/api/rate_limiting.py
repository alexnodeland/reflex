"""Rate limiting configuration for API endpoints.

This module provides rate limiting using slowapi to prevent API abuse.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

if TYPE_CHECKING:
    from fastapi import Request
    from slowapi.errors import RateLimitExceeded

# Rate limiter instance
limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors.

    Args:
        request: The incoming request
        exc: The rate limit exception

    Returns:
        JSON response with 429 status
    """
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )
