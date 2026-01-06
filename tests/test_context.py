"""Tests for DecisionContext."""

import time
from datetime import datetime, timedelta

from reflex.context import DecisionContext
from reflex.events import HTTPEvent, TimerEvent, WebSocketEvent


class TestDecisionContext:
    """Tests for DecisionContext."""

    def test_create(self) -> None:
        """Should create a DecisionContext."""
        ctx = DecisionContext(scope="test")
        assert ctx.scope == "test"
        assert ctx.events == []
        assert ctx.scratch == {}
        assert ctx.created_at is not None

    def test_add_event(self) -> None:
        """Should add events to the context."""
        ctx = DecisionContext(scope="test")
        event = WebSocketEvent(source="test", connection_id="c1", content="hi")

        ctx.add(event)

        assert len(ctx.events) == 1
        assert ctx.events[0].id == event.id

    def test_add_multiple_events(self) -> None:
        """Should add multiple events."""
        ctx = DecisionContext(scope="test")
        events = [
            WebSocketEvent(source="test", connection_id="c1", content="first"),
            WebSocketEvent(source="test", connection_id="c2", content="second"),
        ]

        for event in events:
            ctx.add(event)

        assert len(ctx.events) == 2

    def test_window(self) -> None:
        """Should return events within time window."""
        ctx = DecisionContext(scope="test")

        # Add old event
        old_event = WebSocketEvent(source="test", connection_id="c1", content="old")
        old_event.timestamp = datetime.utcnow() - timedelta(seconds=10)
        ctx.add(old_event)

        # Add recent event
        recent_event = WebSocketEvent(source="test", connection_id="c2", content="recent")
        ctx.add(recent_event)

        # Get events from last 5 seconds
        windowed = ctx.window(5)

        assert len(windowed) == 1
        assert windowed[0].id == recent_event.id

    def test_window_empty(self) -> None:
        """Should return empty list if no events in window."""
        ctx = DecisionContext(scope="test")

        # Add old event
        old_event = WebSocketEvent(source="test", connection_id="c1", content="old")
        old_event.timestamp = datetime.utcnow() - timedelta(seconds=60)
        ctx.add(old_event)

        # Get events from last 5 seconds
        windowed = ctx.window(5)

        assert len(windowed) == 0

    def test_of_type(self) -> None:
        """Should filter events by type."""
        ctx = DecisionContext(scope="test")

        ws_event = WebSocketEvent(source="test", connection_id="c1", content="ws")
        http_event = HTTPEvent(source="test", method="GET", path="/api")
        timer_event = TimerEvent(source="test", timer_name="tick")

        ctx.add(ws_event)
        ctx.add(http_event)
        ctx.add(timer_event)

        # Get only WebSocket events
        ws_events = ctx.of_type("ws.message")
        assert len(ws_events) == 1
        assert ws_events[0].type == "ws.message"

        # Get multiple types
        multi_events = ctx.of_type("ws.message", "http.request")
        assert len(multi_events) == 2

    def test_of_type_empty(self) -> None:
        """Should return empty list if no matching events."""
        ctx = DecisionContext(scope="test")

        ws_event = WebSocketEvent(source="test", connection_id="c1", content="ws")
        ctx.add(ws_event)

        # Get non-existent type
        events = ctx.of_type("file.change")
        assert len(events) == 0

    def test_clear(self) -> None:
        """Should clear events and scratch."""
        ctx = DecisionContext(scope="test")

        ctx.add(WebSocketEvent(source="test", connection_id="c1", content="hi"))
        ctx.scratch["key"] = "value"

        assert len(ctx.events) == 1
        assert len(ctx.scratch) == 1

        ctx.clear()

        assert len(ctx.events) == 0
        assert len(ctx.scratch) == 0

    def test_scratch_storage(self) -> None:
        """Should allow storing scratch data."""
        ctx = DecisionContext(scope="test")

        ctx.scratch["user_id"] = "123"
        ctx.scratch["count"] = 42
        ctx.scratch["data"] = {"nested": "value"}

        assert ctx.scratch["user_id"] == "123"
        assert ctx.scratch["count"] == 42
        assert ctx.scratch["data"]["nested"] == "value"

    def test_summarize(self) -> None:
        """Should create a summary of the context."""
        ctx = DecisionContext(scope="test-scope")

        event = WebSocketEvent(source="ws:client", connection_id="c1", content="hello")
        ctx.add(event)

        summary = ctx.summarize()

        assert "test-scope" in summary
        assert "Events (1)" in summary
        assert "ws.message" in summary
        assert "ws:client" in summary

    def test_summarize_truncates(self) -> None:
        """Should truncate to last 10 events."""
        ctx = DecisionContext(scope="test")

        for i in range(15):
            ctx.add(WebSocketEvent(source="test", connection_id=f"c{i}", content=f"msg{i}"))

        summary = ctx.summarize()

        assert "Events (15)" in summary
        assert "and 5 more events" in summary

    def test_scope_preserved(self) -> None:
        """Scope should not change after creation."""
        ctx = DecisionContext(scope="my-scope")

        ctx.add(WebSocketEvent(source="test", connection_id="c1", content="hi"))
        ctx.clear()

        assert ctx.scope == "my-scope"

    def test_created_at_preserved(self) -> None:
        """created_at should not change."""
        ctx = DecisionContext(scope="test")
        original = ctx.created_at

        time.sleep(0.01)
        ctx.add(WebSocketEvent(source="test", connection_id="c1", content="hi"))

        assert ctx.created_at == original
