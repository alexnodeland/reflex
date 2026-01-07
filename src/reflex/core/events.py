"""Event types with Pydantic discriminated unions.

Events use discriminated unions for efficient O(1) validation.
The discriminator field ('type') is checked first, avoiding
unnecessary validation of non-matching types.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class EventMeta(BaseModel):
    """Trace context for observability.

    Attributes:
        trace_id: Unique identifier for the trace (propagated through Logfire)
        correlation_id: Links related events across a workflow
        causation_id: The event that directly caused this one
    """

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None
    causation_id: str | None = None


class BaseEvent(BaseModel):
    """Base class for all events.

    All events share these fields. The 'type' field is the discriminator
    used for efficient union validation.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = Field(description="Identifier for the event source, e.g., 'ws:client123'")
    meta: EventMeta = Field(default_factory=EventMeta)


# --- Built-in event types ---


class WebSocketEvent(BaseEvent):
    """Event from a WebSocket connection."""

    type: Literal["ws.message"] = "ws.message"
    connection_id: str
    content: str


class HTTPEvent(BaseEvent):
    """Event from an HTTP request."""

    type: Literal["http.request"] = "http.request"
    method: str
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | None = None  # Flexible body type for JSON payloads


class TimerEvent(BaseEvent):
    """Event from a periodic timer."""

    type: Literal["timer.tick"] = "timer.tick"
    timer_name: str
    tick_count: int = 0


class LifecycleEvent(BaseEvent):
    """Internal lifecycle events."""

    type: Literal["lifecycle"] = "lifecycle"
    action: Literal["started", "stopped", "error"]
    details: str | None = None


# --- Discriminated union of all event types ---
#
# Add your custom event types to this union.
# The discriminator='type' tells Pydantic to check the 'type' field first,
# making validation O(1) instead of O(n) for the number of event types.

Event = Annotated[
    WebSocketEvent | HTTPEvent | TimerEvent | LifecycleEvent,
    Field(discriminator="type"),
]
