"""Tests for event types."""

from datetime import UTC, datetime


class TestEventTypes:
    """Tests for event type definitions."""

    def test_websocket_event_creation(self) -> None:
        """Test WebSocketEvent can be created with required fields."""
        from reflex.core.events import WebSocketEvent

        event = WebSocketEvent(
            source="ws:client123",
            connection_id="conn-abc",
            content="Hello, world!",
        )

        assert event.type == "ws.message"
        assert event.source == "ws:client123"
        assert event.connection_id == "conn-abc"
        assert event.content == "Hello, world!"
        assert event.id is not None
        assert event.timestamp is not None
        assert event.meta.trace_id is not None

    def test_http_event_creation(self) -> None:
        """Test HTTPEvent can be created with required fields."""
        from reflex.core.events import HTTPEvent

        event = HTTPEvent(
            source="api:endpoint",
            method="POST",
            path="/api/v1/events",
            headers={"Content-Type": "application/json"},
            body={"key": "value"},
        )

        assert event.type == "http.request"
        assert event.method == "POST"
        assert event.path == "/api/v1/events"
        assert event.headers["Content-Type"] == "application/json"

    def test_timer_event_creation(self) -> None:
        """Test TimerEvent can be created with required fields."""
        from reflex.core.events import TimerEvent

        event = TimerEvent(
            source="timer:heartbeat",
            timer_name="heartbeat",
            tick_count=42,
        )

        assert event.type == "timer.tick"
        assert event.timer_name == "heartbeat"
        assert event.tick_count == 42

    def test_lifecycle_event_creation(self) -> None:
        """Test LifecycleEvent can be created with required fields."""
        from reflex.core.events import LifecycleEvent

        event = LifecycleEvent(
            source="system",
            action="started",
            details="Application started successfully",
        )

        assert event.type == "lifecycle"
        assert event.action == "started"
        assert event.details == "Application started successfully"

    def test_event_meta_defaults(self) -> None:
        """Test EventMeta has sensible defaults."""
        from reflex.core.events import EventMeta

        meta = EventMeta()

        assert meta.trace_id is not None
        assert len(meta.trace_id) > 0
        assert meta.correlation_id is None
        assert meta.causation_id is None

    def test_event_meta_with_values(self) -> None:
        """Test EventMeta can be created with explicit values."""
        from reflex.core.events import EventMeta

        meta = EventMeta(
            trace_id="trace-123",
            correlation_id="corr-456",
            causation_id="cause-789",
        )

        assert meta.trace_id == "trace-123"
        assert meta.correlation_id == "corr-456"
        assert meta.causation_id == "cause-789"


class TestEventDiscriminator:
    """Tests for discriminated union validation."""

    def test_event_union_validation(self) -> None:
        """Test Event discriminated union validates correctly."""
        from pydantic import TypeAdapter

        from reflex.core.events import Event, WebSocketEvent

        adapter: TypeAdapter[Event] = TypeAdapter(Event)

        # Create a WebSocketEvent and serialize it
        event = WebSocketEvent(
            source="ws:test",
            connection_id="conn-1",
            content="test message",
        )
        json_str = event.model_dump_json()

        # Validate from JSON using the union
        parsed = adapter.validate_json(json_str)
        assert isinstance(parsed, WebSocketEvent)
        assert parsed.type == "ws.message"
        assert parsed.content == "test message"

    def test_event_union_discriminates_by_type(self) -> None:
        """Test that discriminator correctly identifies event type."""
        from pydantic import TypeAdapter

        from reflex.core.events import Event, HTTPEvent, TimerEvent

        adapter: TypeAdapter[Event] = TypeAdapter(Event)

        # HTTP event
        http_event = HTTPEvent(source="api", method="GET", path="/")
        http_parsed = adapter.validate_json(http_event.model_dump_json())
        assert isinstance(http_parsed, HTTPEvent)

        # Timer event
        timer_event = TimerEvent(source="timer", timer_name="test")
        timer_parsed = adapter.validate_json(timer_event.model_dump_json())
        assert isinstance(timer_parsed, TimerEvent)


class TestEventSerialization:
    """Tests for event JSON serialization."""

    def test_event_round_trip(self) -> None:
        """Test event can be serialized and deserialized."""
        from reflex.core.events import WebSocketEvent

        original = WebSocketEvent(
            source="ws:client",
            connection_id="conn-abc",
            content="Hello!",
        )

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize from JSON
        restored = WebSocketEvent.model_validate_json(json_str)

        assert restored.id == original.id
        assert restored.type == original.type
        assert restored.source == original.source
        assert restored.connection_id == original.connection_id
        assert restored.content == original.content

    def test_timestamp_serialization(self) -> None:
        """Test timestamp is properly serialized as ISO format."""
        from reflex.core.events import WebSocketEvent

        fixed_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        event = WebSocketEvent(
            source="ws:test",
            connection_id="conn",
            content="test",
            timestamp=fixed_time,
        )

        data = event.model_dump()
        assert data["timestamp"] == fixed_time


class TestEventRegistry:
    """Tests for EventRegistry."""

    def test_builtin_types_registered(self) -> None:
        """Test that built-in event types are registered."""
        from reflex.core.events import EventRegistry

        assert EventRegistry.get("ws.message") is not None
        assert EventRegistry.get("http.request") is not None
        assert EventRegistry.get("timer.tick") is not None
        assert EventRegistry.get("lifecycle") is not None

    def test_all_types_returns_registered(self) -> None:
        """Test all_types returns list of registered classes."""
        from reflex.core.events import (
            EventRegistry,
            HTTPEvent,
            LifecycleEvent,
            TimerEvent,
            WebSocketEvent,
        )

        types = EventRegistry.all_types()
        assert WebSocketEvent in types
        assert HTTPEvent in types
        assert TimerEvent in types
        assert LifecycleEvent in types

    def test_type_names_returns_strings(self) -> None:
        """Test type_names returns list of type strings."""
        from reflex.core.events import EventRegistry

        names = EventRegistry.type_names()
        assert "ws.message" in names
        assert "http.request" in names
        assert "timer.tick" in names
        assert "lifecycle" in names

    def test_parse_websocket_event(self) -> None:
        """Test parsing WebSocket event data."""
        from reflex.core.events import EventRegistry, WebSocketEvent

        data = {
            "type": "ws.message",
            "source": "test",
            "connection_id": "conn-1",
            "content": "hello",
        }
        event = EventRegistry.parse(data)

        assert isinstance(event, WebSocketEvent)
        assert event.source == "test"
        assert event.connection_id == "conn-1"
        assert event.content == "hello"

    def test_parse_http_event(self) -> None:
        """Test parsing HTTP event data."""
        from reflex.core.events import EventRegistry, HTTPEvent

        data = {
            "type": "http.request",
            "source": "api",
            "method": "POST",
            "path": "/test",
        }
        event = EventRegistry.parse(data)

        assert isinstance(event, HTTPEvent)
        assert event.method == "POST"
        assert event.path == "/test"

    def test_parse_missing_type_raises(self) -> None:
        """Test parsing without type field raises ValueError."""
        import pytest

        from reflex.core.events import EventRegistry

        with pytest.raises(ValueError, match="must have 'type' field"):
            EventRegistry.parse({"source": "test"})

    def test_parse_unknown_type_raises(self) -> None:
        """Test parsing unknown type raises ValueError."""
        import pytest

        from reflex.core.events import EventRegistry

        with pytest.raises(ValueError, match="Unknown event type"):
            EventRegistry.parse({"type": "unknown.type", "source": "test"})

    def test_get_returns_none_for_unknown(self) -> None:
        """Test get returns None for unknown type."""
        from reflex.core.events import EventRegistry

        assert EventRegistry.get("nonexistent.type") is None


class TestCustomEventRegistration:
    """Tests for registering custom event types."""

    def test_register_custom_event(self) -> None:
        """Test registering a custom event type."""
        from typing import Literal

        from reflex.core.events import BaseEvent, EventRegistry

        @EventRegistry.register
        class CustomTestEvent(BaseEvent):
            type: Literal["custom.test"] = "custom.test"
            custom_field: str

        try:
            # Should be registered
            assert EventRegistry.get("custom.test") is CustomTestEvent

            # Should be parseable
            event = EventRegistry.parse(
                {
                    "type": "custom.test",
                    "source": "test",
                    "custom_field": "value",
                }
            )
            assert isinstance(event, CustomTestEvent)
            assert event.custom_field == "value"
        finally:
            # Clean up (remove from registry)
            if "custom.test" in EventRegistry._types:
                del EventRegistry._types["custom.test"]

    def test_register_without_type_field_raises(self) -> None:
        """Test registering event without type field raises."""
        import pytest

        from reflex.core.events import BaseEvent, EventRegistry

        with pytest.raises(ValueError, match="must have a 'type' field"):

            @EventRegistry.register
            class InvalidEvent(BaseEvent):
                custom_field: str

    def test_register_duplicate_type_raises(self) -> None:
        """Test registering duplicate type raises."""
        from typing import Literal

        import pytest

        from reflex.core.events import BaseEvent, EventRegistry

        @EventRegistry.register
        class DuplicateTestEvent(BaseEvent):
            type: Literal["duplicate.test"] = "duplicate.test"
            field1: str

        try:
            with pytest.raises(ValueError, match="already registered"):

                @EventRegistry.register
                class AnotherDuplicateEvent(BaseEvent):
                    type: Literal["duplicate.test"] = "duplicate.test"
                    field2: str

        finally:
            # Clean up
            if "duplicate.test" in EventRegistry._types:
                del EventRegistry._types["duplicate.test"]

    def test_reregister_same_class_allowed(self) -> None:
        """Test re-registering the same class is allowed."""
        from typing import Literal

        from reflex.core.events import BaseEvent, EventRegistry

        @EventRegistry.register
        class ReregisterTestEvent(BaseEvent):
            type: Literal["reregister.test"] = "reregister.test"
            field: str

        try:
            # Re-registering same class should not raise
            EventRegistry.register(ReregisterTestEvent)
            assert EventRegistry.get("reregister.test") is ReregisterTestEvent
        finally:
            # Clean up
            if "reregister.test" in EventRegistry._types:
                del EventRegistry._types["reregister.test"]


class TestGetEventUnion:
    """Tests for get_event_union function."""

    def test_get_event_union_returns_type(self) -> None:
        """Test get_event_union returns a type."""
        from reflex.core.events import get_event_union

        union = get_event_union()
        assert union is not None

    def test_get_event_union_includes_builtin(self) -> None:
        """Test union includes built-in types."""
        from pydantic import TypeAdapter

        from reflex.core.events import WebSocketEvent, get_event_union

        union = get_event_union()
        adapter = TypeAdapter(union)

        # Should be able to validate WebSocketEvent
        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        parsed = adapter.validate_python(event.model_dump())
        assert isinstance(parsed, WebSocketEvent)
