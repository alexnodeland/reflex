"""Decision context for working memory during decision-making."""

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from reflex.events import Event


class DecisionContext(BaseModel):
    """Working memory that accumulates events between actions."""

    scope: str
    events: list[Event] = Field(default_factory=list)
    scratch: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def add(self, event: Event) -> None:
        """Add an event to the context."""
        self.events.append(event)

    def window(self, seconds: float) -> list[Event]:
        """Get events within a time window from now."""
        cutoff = datetime.utcnow() - timedelta(seconds=seconds)
        return [e for e in self.events if e.timestamp >= cutoff]

    def of_type(self, *types: str) -> list[Event]:
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
