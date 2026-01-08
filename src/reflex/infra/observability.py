"""Observability configuration with Logfire integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import logfire

from reflex.config import get_settings

if TYPE_CHECKING:
    from fastapi import FastAPI


def configure_observability() -> None:
    """Configure Logfire for observability.

    Call once at application startup.
    """
    settings = get_settings()
    # Console output only in development mode
    console_option = logfire.ConsoleOptions() if settings.environment == "development" else False
    # Only send to Logfire if token is present
    send_to_logfire = "if-token-present" if not settings.logfire_token else True
    logfire.configure(
        token=settings.logfire_token,
        service_name="reflex",
        service_version=settings.version,
        environment=settings.environment,
        console=console_option,
        send_to_logfire=send_to_logfire,
    )


def instrument_app(app: FastAPI) -> None:
    """Instrument FastAPI and all integrations.

    This enables:
    - HTTP request/response tracing
    - PydanticAI agent calls with token usage
    - Database queries
    - Outgoing HTTP requests
    - Full distributed tracing across all layers
    """
    logfire.instrument_fastapi(app)
    logfire.instrument_pydantic_ai()
    logfire.instrument_asyncpg()
    logfire.instrument_httpx()
