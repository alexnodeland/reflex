"""Event types with discriminated unions for efficient validation."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


class EventMeta(BaseModel):
    """Trace context for observability."""

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None
    causation_id: str | None = None


class BaseEvent(BaseModel):
    """Common fields for all events."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=_utc_now)
    source: str
    meta: EventMeta = Field(default_factory=EventMeta)


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
    body: dict[str, object] | None = None


class FileEvent(BaseEvent):
    """Event from a file system change."""

    type: Literal["file.change"] = "file.change"
    path: str
    change_type: Literal["created", "modified", "deleted"]


class TimerEvent(BaseEvent):
    """Event from a timer tick."""

    type: Literal["timer.tick"] = "timer.tick"
    timer_name: str


# Discriminated union - validator checks 'type' first
Event = Annotated[
    WebSocketEvent | HTTPEvent | FileEvent | TimerEvent,
    Field(discriminator="type"),
]
