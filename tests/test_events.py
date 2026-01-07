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
