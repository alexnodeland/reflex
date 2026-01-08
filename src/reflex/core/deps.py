"""Dependency injection for agents.

Provides typed dependencies to PydanticAI agents via RunContext.

This module provides focused dependency containers:
- StorageContext: Database and event store access
- NetworkContext: HTTP client for external calls
- ExecutionContext: Execution metadata (scope, tracing)
- ReflexDeps: Combined container with backward-compatible interface
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

    from reflex.infra.store import EventStore


@dataclass(frozen=True)
class StorageContext:
    """Storage-related dependencies.

    Provides access to event store and database sessions.

    Attributes:
        store: EventStore for event persistence and publishing
        db: Database session for direct queries
    """

    store: EventStore
    db: AsyncSession


@dataclass(frozen=True)
class NetworkContext:
    """Network-related dependencies.

    Provides access to HTTP clients for external API calls.

    Attributes:
        http: Async HTTP client for external API calls
    """

    http: httpx.AsyncClient


@dataclass(frozen=True)
class ExecutionContext:
    """Execution metadata.

    Provides context information for tracing and scoping.

    Attributes:
        scope: Current execution scope (for context/logging)
        trace_id: Trace ID for distributed tracing
        correlation_id: Correlation ID for request correlation
    """

    scope: str
    trace_id: str | None = None
    correlation_id: str | None = None


@dataclass
class ReflexDeps:
    """Core dependencies for agent execution.

    These dependencies are available in PydanticAI tools via
    RunContext[ReflexDeps].

    This class maintains backward compatibility while internally
    organizing dependencies into focused contexts.

    Attributes:
        store: EventStore for event persistence and publishing
        http: Async HTTP client for external API calls
        db: Database session for direct queries
        scope: Current execution scope (for context/logging)
        trace_id: Trace ID for distributed tracing (optional)
        correlation_id: Correlation ID for request correlation (optional)

    Example:
        @alert_agent.tool
        async def get_recent_events(
            ctx: RunContext[ReflexDeps],
            event_type: str | None = None,
        ) -> str:
            store = ctx.deps.store
            # Use store to fetch events...

    Alternative usage with contexts:
        deps = ReflexDeps(store=store, http=http, db=db, scope="api:/events")
        storage = deps.storage  # StorageContext
        network = deps.network  # NetworkContext
        execution = deps.execution  # ExecutionContext
    """

    store: EventStore
    http: httpx.AsyncClient
    db: AsyncSession
    scope: str
    trace_id: str | None = None
    correlation_id: str | None = None

    @property
    def storage(self) -> StorageContext:
        """Get storage context with store and db."""
        return StorageContext(store=self.store, db=self.db)

    @property
    def network(self) -> NetworkContext:
        """Get network context with HTTP client."""
        return NetworkContext(http=self.http)

    @property
    def execution(self) -> ExecutionContext:
        """Get execution context with scope and tracing info."""
        return ExecutionContext(
            scope=self.scope,
            trace_id=self.trace_id,
            correlation_id=self.correlation_id,
        )

    @classmethod
    def from_contexts(
        cls,
        storage: StorageContext,
        network: NetworkContext,
        execution: ExecutionContext,
    ) -> ReflexDeps:
        """Create ReflexDeps from individual contexts.

        This factory method allows creating ReflexDeps from the
        focused context objects for flexibility.

        Args:
            storage: Storage context with store and db
            network: Network context with HTTP client
            execution: Execution context with scope and tracing

        Returns:
            ReflexDeps instance with all dependencies
        """
        return cls(
            store=storage.store,
            http=network.http,
            db=storage.db,
            scope=execution.scope,
            trace_id=execution.trace_id,
            correlation_id=execution.correlation_id,
        )
