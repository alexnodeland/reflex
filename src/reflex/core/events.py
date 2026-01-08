"""Event types with Pydantic discriminated unions.

Events use discriminated unions for efficient O(1) validation.
The discriminator field ('type') is checked first, avoiding
unnecessary validation of non-matching types.

Custom event types can be registered at runtime using EventRegistry:

    from reflex.core.events import BaseEvent, EventRegistry

    @EventRegistry.register
    class MyCustomEvent(BaseEvent):
        type: Literal["my.custom"] = "my.custom"
        custom_field: str
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, ClassVar, Literal, TypeVar, Union
from uuid import uuid4

from pydantic import BaseModel, Field

# Type variable for preserving event class types in registry
_EventT = TypeVar("_EventT", bound="BaseEvent")


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

    Subclasses must define a `type` field with a Literal type, e.g.:
        type: Literal["my.custom"] = "my.custom"
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = Field(description="Identifier for the event source, e.g., 'ws:client123'")
    meta: EventMeta = Field(default_factory=EventMeta)


class EventRegistry:
    """Registry for event types.

    Allows dynamic registration of event types at runtime.
    Built-in event types are automatically registered.

    Example:
        @EventRegistry.register
        class MyCustomEvent(BaseEvent):
            type: Literal["my.custom"] = "my.custom"
            custom_field: str

        # Later, parse events including custom types
        data = {"type": "my.custom", "source": "test", "custom_field": "value"}
        event = EventRegistry.parse(data)
    """

    _types: ClassVar[dict[str, type[BaseEvent]]] = {}

    @classmethod
    def register(cls, event_class: type[_EventT]) -> type[_EventT]:
        """Register an event type. Can be used as decorator.

        Args:
            event_class: The event class to register

        Returns:
            The registered event class (for decorator usage)

        Raises:
            ValueError: If class has no 'type' field or type is already registered
        """
        # Get the type discriminator value
        type_field = event_class.model_fields.get("type")
        if type_field is None or type_field.default is None:
            msg = f"Event class {event_class.__name__} must have a 'type' field with default value"
            raise ValueError(msg)

        type_value = type_field.default
        if type_value in cls._types:
            # Allow re-registration of the same class (for module reloads)
            if cls._types[type_value] is not event_class:
                existing = cls._types[type_value].__name__
                msg = f"Event type '{type_value}' already registered by {existing}"
                raise ValueError(msg)
            return event_class

        cls._types[type_value] = event_class
        return event_class

    @classmethod
    def get(cls, type_value: str) -> type[BaseEvent] | None:
        """Get event class by type value.

        Args:
            type_value: The event type string (e.g., "ws.message")

        Returns:
            The event class, or None if not found
        """
        return cls._types.get(type_value)

    @classmethod
    def all_types(cls) -> list[type[BaseEvent]]:
        """Get all registered event types.

        Returns:
            List of all registered event classes
        """
        return list(cls._types.values())

    @classmethod
    def type_names(cls) -> list[str]:
        """Get all registered type names.

        Returns:
            List of all registered type name strings
        """
        return list(cls._types.keys())

    @classmethod
    def parse(cls, data: dict[str, Any]) -> BaseEvent:
        """Parse event data into appropriate event type.

        Args:
            data: Dictionary with event data including 'type' field

        Returns:
            Parsed event instance of the appropriate type

        Raises:
            ValueError: If 'type' field is missing or unknown
        """
        event_type = data.get("type")
        if event_type is None:
            msg = "Event data must have 'type' field"
            raise ValueError(msg)

        event_class = cls._types.get(event_type)
        if event_class is None:
            msg = f"Unknown event type: {event_type}. Registered types: {list(cls._types.keys())}"
            raise ValueError(msg)

        return event_class.model_validate(data)

    @classmethod
    def clear(cls) -> None:
        """Clear all registered types. Mainly for testing."""
        cls._types.clear()


# --- Built-in event types ---


@EventRegistry.register
class WebSocketEvent(BaseEvent):
    """Event from a WebSocket connection."""

    type: Literal["ws.message"] = "ws.message"
    connection_id: str
    content: str


@EventRegistry.register
class HTTPEvent(BaseEvent):
    """Event from an HTTP request."""

    type: Literal["http.request"] = "http.request"
    method: str
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | None = None  # Flexible body type for JSON payloads


@EventRegistry.register
class TimerEvent(BaseEvent):
    """Event from a periodic timer."""

    type: Literal["timer.tick"] = "timer.tick"
    timer_name: str
    tick_count: int = 0


@EventRegistry.register
class LifecycleEvent(BaseEvent):
    """Internal lifecycle events."""

    type: Literal["lifecycle"] = "lifecycle"
    action: Literal["started", "stopped", "error"]
    details: str | None = None


# --- Dynamic event union ---


def get_event_union() -> type:
    """Get the current Event union type including all registered types.

    This returns a Pydantic Annotated union of all registered event types.
    Use this when you need to validate events that may include custom types.

    Returns:
        Annotated union type with discriminator

    Example:
        DynamicEvent = get_event_union()
        event = TypeAdapter(DynamicEvent).validate_python(data)
    """
    types = EventRegistry.all_types()
    if not types:
        return BaseEvent
    # Create union of all registered types
    # Using Union[tuple()] for dynamic union creation - UP007 doesn't apply here
    union_type = Union[tuple(types)]  # type: ignore[valid-type]  # noqa: UP007
    return Annotated[union_type, Field(discriminator="type")]  # type: ignore[return-value]


# --- Static discriminated union for type checking ---
#
# This static union is kept for backward compatibility and better IDE support.
# The discriminator='type' tells Pydantic to check the 'type' field first,
# making validation O(1) instead of O(n) for the number of event types.
#
# For runtime validation of events including custom types, use EventRegistry.parse()
# or get_event_union().

Event = Annotated[
    WebSocketEvent | HTTPEvent | TimerEvent | LifecycleEvent,
    Field(discriminator="type"),
]
