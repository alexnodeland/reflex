"""Trigger system for event-to-agent mapping.

Triggers connect event filters to agents, determining which
agent should handle which events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from reflex.agent.base import Agent
    from reflex.agent.filters import EventFilter
    from reflex.core.events import Event


@dataclass
class Trigger:
    """Maps events to agents via filters.

    A trigger defines:
    - Which events to match (filter)
    - Which agent to execute (agent)
    - How to scope concurrent executions (scope_key)

    The scope_key function extracts a key from the event that
    determines the locking scope. Events with the same scope
    are processed serially to prevent race conditions.

    Example:
        trigger = Trigger(
            name="chat_handler",
            filter=TypeFilter(types=["ws.message"]),
            agent=ChatAgent(),
            scope_key=lambda e: f"user:{e.connection_id}",
        )
    """

    name: str
    filter: EventFilter
    agent: Agent
    scope_key: Callable[[Event], str] = field(default=lambda e: e.source)
    priority: int = 0  # Higher priority triggers execute first

    def matches(self, event: Event) -> bool:
        """Check if this trigger matches the event."""
        return self.filter.matches(event)

    def get_scope(self, event: Event) -> str:
        """Get the locking scope for this event."""
        return self.scope_key(event)


class TriggerRegistry:
    """Registry for managing triggers.

    Maintains a collection of triggers and provides efficient
    lookup for matching events.

    Example:
        registry = TriggerRegistry()
        registry.register(chat_trigger)
        registry.register(analytics_trigger)

        for trigger in registry.match(event):
            await trigger.agent.run(ctx)
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._triggers: list[Trigger] = []

    def register(self, trigger: Trigger) -> None:
        """Register a trigger.

        Args:
            trigger: The trigger to register
        """
        self._triggers.append(trigger)
        # Keep sorted by priority (descending)
        self._triggers.sort(key=lambda t: -t.priority)

    def unregister(self, name: str) -> bool:
        """Unregister a trigger by name.

        Args:
            name: The name of the trigger to remove

        Returns:
            True if trigger was found and removed, False otherwise
        """
        for i, trigger in enumerate(self._triggers):
            if trigger.name == name:
                del self._triggers[i]
                return True
        return False

    def match(self, event: Event) -> list[Trigger]:
        """Find all triggers matching the event.

        Returns triggers in priority order (highest first).

        Args:
            event: The event to match against

        Returns:
            List of matching triggers, sorted by priority
        """
        return [t for t in self._triggers if t.matches(event)]

    def get(self, name: str) -> Trigger | None:
        """Get a trigger by name.

        Args:
            name: The trigger name

        Returns:
            The trigger if found, None otherwise
        """
        for trigger in self._triggers:
            if trigger.name == name:
                return trigger
        return None

    @property
    def triggers(self) -> list[Trigger]:
        """Get all registered triggers."""
        return list(self._triggers)

    def clear(self) -> None:
        """Remove all triggers."""
        self._triggers.clear()


# Global registry instance
_registry = TriggerRegistry()


def register_trigger(trigger: Trigger) -> None:
    """Register a trigger in the global registry."""
    _registry.register(trigger)


def get_registry() -> TriggerRegistry:
    """Get the global trigger registry."""
    return _registry


def trigger(
    name: str,
    filter: EventFilter,
    scope_key: Callable[[Any], str] | None = None,
    priority: int = 0,
) -> Callable[[type[Agent]], type[Agent]]:
    """Decorator to register an agent class as a trigger.

    Example:
        @trigger("chat_handler", TypeFilter(types=["ws.message"]))
        class ChatAgent(BaseAgent):
            async def run(self, ctx: AgentContext) -> None:
                ...
    """

    def decorator(agent_cls: type[Agent]) -> type[Agent]:
        agent_instance = agent_cls()
        t = Trigger(
            name=name,
            filter=filter,
            agent=agent_instance,
            scope_key=scope_key or (lambda e: e.source),
            priority=priority,
        )
        register_trigger(t)
        return agent_cls

    return decorator
