"""FastAPI dependency injection for API routes.

Provides dependency functions for accessing shared resources
like the EventStore, HTTP client, and database sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from reflex.core.deps import ReflexDeps
from reflex.infra.store import EventStore


def get_store(request: Request) -> EventStore:
    """Get the EventStore from app state.

    Args:
        request: The current request

    Returns:
        The shared EventStore instance
    """
    return request.app.state.store  # type: ignore[no-any-return]


def get_http(request: Request) -> httpx.AsyncClient:
    """Get the HTTP client from app state.

    Args:
        request: The current request

    Returns:
        The shared httpx.AsyncClient instance
    """
    return request.app.state.http  # type: ignore[no-any-return]


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Get a database session for the request.

    Creates a new session for each request and ensures
    proper cleanup after the request completes.

    Args:
        request: The current request

    Yields:
        A new AsyncSession for this request
    """
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


async def get_deps(
    request: Request,
    store: Annotated[EventStore, Depends(get_store)],
    http: Annotated[httpx.AsyncClient, Depends(get_http)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReflexDeps:
    """Get ReflexDeps for use in route handlers.

    Combines all dependencies into a ReflexDeps instance
    that can be passed to agents or other components.

    Args:
        request: The current request
        store: The EventStore dependency
        http: The HTTP client dependency
        db: The database session dependency

    Returns:
        A ReflexDeps instance with all dependencies
    """
    return ReflexDeps(
        store=store,
        http=http,
        db=db,
        scope=f"api:{request.url.path}",
    )


# Type aliases for cleaner route signatures
StoreDep = Annotated[EventStore, Depends(get_store)]
HttpDep = Annotated[httpx.AsyncClient, Depends(get_http)]
DbDep = Annotated[AsyncSession, Depends(get_db)]
DepsDep = Annotated[ReflexDeps, Depends(get_deps)]
