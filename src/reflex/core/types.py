"""Protocol definitions for cross-module type hints.

This module provides Protocol classes that define interfaces for
key types, allowing modules to reference types without creating
circular import dependencies.

The protocols define the minimal interface needed for type checking,
while concrete implementations remain in their respective modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime


@runtime_checkable
class EventProtocol(Protocol):
    """Protocol for event objects.

    Defines the minimal interface that all events must implement.
    Use this for type hints when you need to avoid importing
    concrete Event types.
    """

    id: str
    type: str
    source: str
    timestamp: datetime

    def model_dump_json(self) -> str:
        """Serialize the event to JSON."""
        ...


class EventMetaProtocol(Protocol):
    """Protocol for event metadata."""

    correlation_id: str | None
    causation_id: str | None
    trace_id: str | None


@runtime_checkable
class EventWithMetaProtocol(EventProtocol, Protocol):
    """Protocol for events with metadata."""

    meta: EventMetaProtocol


class EventStoreProtocol(Protocol):
    """Protocol for event store operations.

    Defines the interface for event persistence and subscription.
    Use this for type hints when you need to avoid importing
    the concrete EventStore class.
    """

    async def publish(self, event: EventProtocol) -> None:
        """Persist event and notify subscribers."""
        ...

    async def ack(self, token: str) -> None:
        """Mark event as successfully processed."""
        ...

    async def nack(self, token: str, error: str | None = None) -> None:
        """Mark event as failed with retry logic."""
        ...

    def subscribe(
        self,
        event_types: list[str] | None = None,
        batch_size: int = 100,
    ) -> AsyncIterator[tuple[Any, str]]:
        """Subscribe to events, yielding (event, token) pairs."""
        ...

    def replay(
        self,
        start: datetime,
        end: datetime | None = None,
        event_types: list[str] | None = None,
    ) -> AsyncIterator[Any]:
        """Replay historical events."""
        ...

    async def dlq_list(self, limit: int = 100) -> list[Any]:
        """List events in dead-letter queue."""
        ...

    async def dlq_retry(self, event_id: str) -> bool:
        """Move event from DLQ back to pending."""
        ...


class LockBackendProtocol(Protocol):
    """Protocol for lock backend operations."""

    async def acquire(self, scope: str, wait_timeout: float | None = None) -> bool:
        """Acquire lock for scope."""
        ...

    async def release(self, scope: str) -> None:
        """Release lock for scope."""
        ...

    async def is_locked(self, scope: str) -> bool:
        """Check if scope is locked."""
        ...

    async def close(self) -> None:
        """Close the backend and release resources."""
        ...
