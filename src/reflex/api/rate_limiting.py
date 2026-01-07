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

    from reflex.config import Settings


def create_limiter(settings: Settings | None = None) -> Limiter:
    """Create a rate limiter instance.

    Factory function that creates a limiter based on settings.
    If settings is None, creates a limiter with default configuration.

    Args:
        settings: Optional Settings instance for configuration

    Returns:
        Configured Limiter instance

    Example:
        # Create from settings
        limiter = create_limiter(get_settings())

        # Create with defaults (for testing or simple cases)
        limiter = create_limiter()
    """
    if settings is not None:
        default_limit = f"{settings.rate_limit_requests}/{settings.rate_limit_window}second"
    else:
        default_limit = "100/60second"  # Default: 100 requests per minute

    return Limiter(
        key_func=get_remote_address,
        default_limits=[default_limit],  # type: ignore[list-item]
    )


# Default limiter instance for backward compatibility
# New code should use create_limiter() instead
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
