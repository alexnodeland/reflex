"""Tests for event types and discriminated unions."""

from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from reflex.events import (
    BaseEvent,
    Event,
    EventMeta,
    FileEvent,
    HTTPEvent,
    TimerEvent,
    WebSocketEvent,
)


class TestEventMeta:
    """Tests for EventMeta."""

    def test_default_trace_id(self) -> None:
        """Should generate a trace_id by default."""
        meta = EventMeta()
        assert meta.trace_id is not None
        assert len(meta.trace_id) == 36  # UUID format

    def test_default_optional_fields(self) -> None:
        """Should have None for optional fields by default."""
        meta = EventMeta()
        assert meta.correlation_id is None
        assert meta.causation_id is None

    def test_explicit_values(self) -> None:
        """Should accept explicit values."""
        meta = EventMeta(
            trace_id="trace-123",
            correlation_id="corr-456",
            causation_id="cause-789",
        )
        assert meta.trace_id == "trace-123"
        assert meta.correlation_id == "corr-456"
        assert meta.causation_id == "cause-789"


class TestBaseEvent:
    """Tests for BaseEvent."""

    def test_default_id(self) -> None:
        """Should generate an id by default."""

        class TestEvent(BaseEvent):
            type: str = "test"

        event = TestEvent(source="test")
        assert event.id is not None
        assert len(event.id) == 36  # UUID format

    def test_default_timestamp(self) -> None:
        """Should generate a timestamp by default."""

        class TestEvent(BaseEvent):
            type: str = "test"

        before = datetime.now(UTC)
        event = TestEvent(source="test")
        after = datetime.now(UTC)
        assert before <= event.timestamp <= after

    def test_default_meta(self) -> None:
        """Should generate EventMeta by default."""

        class TestEvent(BaseEvent):
            type: str = "test"

        event = TestEvent(source="test")
        assert event.meta is not None
        assert event.meta.trace_id is not None


class TestWebSocketEvent:
    """Tests for WebSocketEvent."""

    def test_create(self) -> None:
        """Should create a WebSocketEvent."""
        event = WebSocketEvent(
            source="ws:client1",
            connection_id="conn-123",
            content="Hello, world!",
        )
        assert event.type == "ws.message"
        assert event.source == "ws:client1"
        assert event.connection_id == "conn-123"
        assert event.content == "Hello, world!"

    def test_type_is_literal(self) -> None:
        """Type should always be 'ws.message'."""
        event = WebSocketEvent(
            source="test",
            connection_id="conn",
            content="test",
        )
        assert event.type == "ws.message"


class TestHTTPEvent:
    """Tests for HTTPEvent."""

    def test_create(self) -> None:
        """Should create an HTTPEvent."""
        event = HTTPEvent(
            source="http:api",
            method="POST",
            path="/api/users",
            body={"name": "Alice"},
        )
        assert event.type == "http.request"
        assert event.method == "POST"
        assert event.path == "/api/users"
        assert event.body == {"name": "Alice"}

    def test_body_optional(self) -> None:
        """Body should be optional."""
        event = HTTPEvent(
            source="http:api",
            method="GET",
            path="/api/users",
        )
        assert event.body is None


class TestFileEvent:
    """Tests for FileEvent."""

    def test_create(self) -> None:
        """Should create a FileEvent."""
        event = FileEvent(
            source="fs:watcher",
            path="/tmp/test.txt",
            change_type="created",
        )
        assert event.type == "file.change"
        assert event.path == "/tmp/test.txt"
        assert event.change_type == "created"

    def test_change_type_validation(self) -> None:
        """Should validate change_type literal."""
        for change_type in ["created", "modified", "deleted"]:
            event = FileEvent(
                source="fs",
                path="/tmp/test.txt",
                change_type=change_type,  # type: ignore[arg-type]
            )
            assert event.change_type == change_type


class TestTimerEvent:
    """Tests for TimerEvent."""

    def test_create(self) -> None:
        """Should create a TimerEvent."""
        event = TimerEvent(
            source="timer:heartbeat",
            timer_name="heartbeat",
        )
        assert event.type == "timer.tick"
        assert event.timer_name == "heartbeat"


class TestDiscriminatedUnion:
    """Tests for the Event discriminated union."""

    def test_parse_websocket_event(self) -> None:
        """Should parse WebSocketEvent from JSON."""
        adapter: TypeAdapter[Event] = TypeAdapter(Event)
        data = {
            "type": "ws.message",
            "source": "test",
            "connection_id": "conn-1",
            "content": "hello",
        }
        event = adapter.validate_python(data)
        assert isinstance(event, WebSocketEvent)
        assert event.connection_id == "conn-1"

    def test_parse_http_event(self) -> None:
        """Should parse HTTPEvent from JSON."""
        adapter: TypeAdapter[Event] = TypeAdapter(Event)
        data = {
            "type": "http.request",
            "source": "test",
            "method": "GET",
            "path": "/api",
        }
        event = adapter.validate_python(data)
        assert isinstance(event, HTTPEvent)
        assert event.method == "GET"

    def test_parse_file_event(self) -> None:
        """Should parse FileEvent from JSON."""
        adapter: TypeAdapter[Event] = TypeAdapter(Event)
        data = {
            "type": "file.change",
            "source": "test",
            "path": "/tmp/file.txt",
            "change_type": "modified",
        }
        event = adapter.validate_python(data)
        assert isinstance(event, FileEvent)
        assert event.change_type == "modified"

    def test_parse_timer_event(self) -> None:
        """Should parse TimerEvent from JSON."""
        adapter: TypeAdapter[Event] = TypeAdapter(Event)
        data = {
            "type": "timer.tick",
            "source": "test",
            "timer_name": "cron",
        }
        event = adapter.validate_python(data)
        assert isinstance(event, TimerEvent)
        assert event.timer_name == "cron"

    def test_invalid_type_raises(self) -> None:
        """Should raise ValidationError for unknown type."""
        adapter: TypeAdapter[Event] = TypeAdapter(Event)
        data = {
            "type": "unknown.event",
            "source": "test",
        }
        with pytest.raises(ValidationError):
            adapter.validate_python(data)

    def test_roundtrip_serialization(self) -> None:
        """Should serialize and deserialize correctly."""
        adapter: TypeAdapter[Event] = TypeAdapter(Event)
        original = WebSocketEvent(
            source="test",
            connection_id="conn-1",
            content="hello",
        )
        json_str = original.model_dump_json()
        parsed = adapter.validate_json(json_str)
        assert isinstance(parsed, WebSocketEvent)
        assert parsed.id == original.id
        assert parsed.connection_id == original.connection_id
