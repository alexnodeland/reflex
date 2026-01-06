"""Typed dependency container for PydanticAI agents."""

from dataclasses import dataclass

import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from reflex.store import EventStore


@dataclass
class ReflexDeps:
    """Dependencies injected into agents."""

    event_store: EventStore
    http: httpx.AsyncClient
    db: AsyncSession | None
    scope: str
