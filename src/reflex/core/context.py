"""Agent execution context.

Provides typed dependencies to agents during execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from reflex.core.events import Event
    from reflex.infra.store import EventStore


@dataclass
class AgentContext:
    """Context provided to agents during execution.

    Contains the triggering event and typed dependencies for
    database access, event publishing, and external services.

    Attributes:
        event: The event that triggered this agent execution
        store: EventStore for persistence operations
        publish: Async function to publish new events
        scope: The scope key for this execution (for locking)
    """

    event: Event
    store: EventStore
    publish: Callable[[Any], Coroutine[Any, Any, None]]
    scope: str

    def derive_event(self, **kwargs: Any) -> dict[str, Any]:
        """Create event data derived from the current event.

        Automatically sets causation_id and correlation_id for tracing.

        Args:
            **kwargs: Additional fields for the new event

        Returns:
            Dict with meta fields set for event derivation
        """
        return {
            "meta": {
                "causation_id": self.event.id,
                "correlation_id": self.event.meta.correlation_id or self.event.id,
                "trace_id": self.event.meta.trace_id,
            },
            **kwargs,
        }
