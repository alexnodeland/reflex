"""Dependency injection for agents.

Provides typed dependencies to PydanticAI agents via RunContext.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

    from reflex.infra.store import EventStore


@dataclass
class ReflexDeps:
    """Core dependencies for agent execution.

    These dependencies are available in PydanticAI tools via
    RunContext[ReflexDeps].

    Attributes:
        store: EventStore for event persistence and publishing
        http: Async HTTP client for external API calls
        db: Database session for direct queries
        scope: Current execution scope (for context/logging)

    Example:
        @alert_agent.tool
        async def get_recent_events(
            ctx: RunContext[ReflexDeps],
            event_type: str | None = None,
        ) -> str:
            store = ctx.deps.store
            # Use store to fetch events...
    """

    store: EventStore
    http: httpx.AsyncClient
    db: AsyncSession
    scope: str
