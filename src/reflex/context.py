"""Decision context for working memory during decision-making."""

from datetime import UTC, datetime, timedelta
from typing import Any, TypeAlias

from pydantic import BaseModel, Field

from reflex.events import Event, FileEvent, HTTPEvent, TimerEvent, WebSocketEvent

# Type alias for the event union
EventType: TypeAlias = WebSocketEvent | HTTPEvent | FileEvent | TimerEvent


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _empty_event_list() -> list[EventType]:
    return []


class DecisionContext(BaseModel):
    """Working memory that accumulates events between actions."""

    scope: str
    events: list[EventType] = Field(default_factory=_empty_event_list)
    scratch: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)

    def add(self, event: Event) -> None:
        """Add an event to the context."""
        self.events.append(event)

    def window(self, seconds: float) -> list[EventType]:
        """Get events within a time window from now."""
        cutoff = _utc_now() - timedelta(seconds=seconds)
        return [e for e in self.events if e.timestamp >= cutoff]

    def of_type(self, *types: str) -> list[EventType]:
        """Get events of specific types."""
        return [e for e in self.events if e.type in types]

    def clear(self) -> None:
        """Clear all events and scratch data."""
        self.events.clear()
        self.scratch.clear()

    def summarize(self) -> str:
        """Create a summary of the context for agent prompts."""
        lines = [f"Scope: {self.scope}", f"Events ({len(self.events)}):"]
        for event in self.events[-10:]:  # Last 10 events
            lines.append(f"  - [{event.type}] {event.source}: {event.model_dump_json()[:100]}")
        if len(self.events) > 10:
            lines.append(f"  ... and {len(self.events) - 10} more events")
        return "\n".join(lines)
