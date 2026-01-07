"""Tests for agent context."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from reflex.core.context import AgentContext, DecisionContext
from reflex.core.events import (
    EventMeta,
    HTTPEvent,
    TimerEvent,
    WebSocketEvent,
)


class TestAgentContext:
    """Tests for AgentContext class."""

    def test_context_creation(self) -> None:
        """Test creating an agent context."""
        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        store = AsyncMock()
        publish = AsyncMock()

        ctx = AgentContext(
            event=event,
            store=store,
            publish=publish,
            scope="test:scope",
        )

        assert ctx.event is event
        assert ctx.store is store
        assert ctx.publish is publish
        assert ctx.scope == "test:scope"

    def test_derive_event_sets_causation(self) -> None:
        """Test that derive_event sets causation_id."""
        event = WebSocketEvent(
            id="event-123",
            source="test",
            connection_id="1",
            content="hi",
        )
        store = AsyncMock()
        publish = AsyncMock()

        ctx = AgentContext(
            event=event,
            store=store,
            publish=publish,
            scope="test",
        )

        derived = ctx.derive_event(foo="bar")

        assert derived["meta"]["causation_id"] == "event-123"
        assert derived["foo"] == "bar"

    def test_derive_event_sets_correlation(self) -> None:
        """Test that derive_event sets correlation_id."""
        # Event without correlation_id - should use event id
        event1 = WebSocketEvent(
            id="event-123",
            source="test",
            connection_id="1",
            content="hi",
        )
        ctx1 = AgentContext(
            event=event1,
            store=AsyncMock(),
            publish=AsyncMock(),
            scope="test",
        )
        derived1 = ctx1.derive_event()
        assert derived1["meta"]["correlation_id"] == "event-123"

        # Event with correlation_id - should preserve it
        event2 = WebSocketEvent(
            id="event-456",
            source="test",
            connection_id="1",
            content="hi",
            meta=EventMeta(correlation_id="corr-789"),
        )
        ctx2 = AgentContext(
            event=event2,
            store=AsyncMock(),
            publish=AsyncMock(),
            scope="test",
        )
        derived2 = ctx2.derive_event()
        assert derived2["meta"]["correlation_id"] == "corr-789"

    def test_derive_event_preserves_trace_id(self) -> None:
        """Test that derive_event preserves trace_id."""
        event = WebSocketEvent(
            source="test",
            connection_id="1",
            content="hi",
            meta=EventMeta(trace_id="trace-abc"),
        )
        ctx = AgentContext(
            event=event,
            store=AsyncMock(),
            publish=AsyncMock(),
            scope="test",
        )

        derived = ctx.derive_event()
        assert derived["meta"]["trace_id"] == "trace-abc"

    def test_derive_event_with_extra_fields(self) -> None:
        """Test derive_event with additional fields."""
        event = WebSocketEvent(
            id="event-123",
            source="test",
            connection_id="1",
            content="hi",
        )
        ctx = AgentContext(
            event=event,
            store=AsyncMock(),
            publish=AsyncMock(),
            scope="test",
        )

        derived = ctx.derive_event(
            source="agent:processor",
            custom_field="custom_value",
            nested={"key": "value"},
        )

        assert derived["source"] == "agent:processor"
        assert derived["custom_field"] == "custom_value"
        assert derived["nested"] == {"key": "value"}
        assert "meta" in derived  # Meta should still be set


class TestDecisionContext:
    """Tests for DecisionContext class."""

    def test_empty_context_creation(self) -> None:
        """Test creating an empty decision context."""
        ctx = DecisionContext()
        assert ctx.events == []
        assert ctx.last_action_time is None

    def test_add_event(self) -> None:
        """Test adding events to context."""
        ctx = DecisionContext()
        event1 = WebSocketEvent(source="test", connection_id="1", content="hello")
        event2 = WebSocketEvent(source="test", connection_id="1", content="world")

        ctx.add(event1)
        ctx.add(event2)

        assert len(ctx.events) == 2
        assert ctx.events[0] is event1
        assert ctx.events[1] is event2

    def test_window_returns_recent_events(self) -> None:
        """Test window returns events within time window."""
        ctx = DecisionContext()
        now = datetime.now(UTC)

        # Add events with different timestamps
        old_event = WebSocketEvent(
            source="test",
            connection_id="1",
            content="old",
            timestamp=now - timedelta(seconds=120),
        )
        recent_event = WebSocketEvent(
            source="test",
            connection_id="1",
            content="recent",
            timestamp=now - timedelta(seconds=30),
        )
        very_recent = WebSocketEvent(
            source="test",
            connection_id="1",
            content="very_recent",
            timestamp=now,
        )

        ctx.add(old_event)
        ctx.add(recent_event)
        ctx.add(very_recent)

        # Window of 60 seconds should return 2 events
        windowed = ctx.window(60)
        assert len(windowed) == 2
        assert recent_event in windowed
        assert very_recent in windowed
        assert old_event not in windowed

    def test_of_type_filters_events(self) -> None:
        """Test of_type returns events matching types."""
        ctx = DecisionContext()

        ws_event = WebSocketEvent(source="test", connection_id="1", content="ws")
        http_event = HTTPEvent(source="test", method="GET", path="/")
        timer_event = TimerEvent(source="test", timer_name="tick")

        ctx.add(ws_event)
        ctx.add(http_event)
        ctx.add(timer_event)

        # Filter by single type
        ws_only = ctx.of_type("ws.message")
        assert len(ws_only) == 1
        assert ws_only[0] is ws_event

        # Filter by multiple types
        ws_and_http = ctx.of_type("ws.message", "http.request")
        assert len(ws_and_http) == 2

    def test_since_last_action_all_events_when_no_action(self) -> None:
        """Test since_last_action returns all events when no action taken."""
        ctx = DecisionContext()

        event1 = WebSocketEvent(source="test", connection_id="1", content="1")
        event2 = WebSocketEvent(source="test", connection_id="1", content="2")

        ctx.add(event1)
        ctx.add(event2)

        since_action = ctx.since_last_action()
        assert len(since_action) == 2

    def test_since_last_action_after_mark(self) -> None:
        """Test since_last_action returns events after mark_action."""
        ctx = DecisionContext()
        now = datetime.now(UTC)

        old_event = WebSocketEvent(
            source="test",
            connection_id="1",
            content="old",
            timestamp=now - timedelta(seconds=10),
        )
        ctx.add(old_event)

        # Mark action
        ctx.mark_action()

        # Add new event after action
        new_event = WebSocketEvent(
            source="test",
            connection_id="1",
            content="new",
            timestamp=now + timedelta(seconds=1),
        )
        ctx.add(new_event)

        since_action = ctx.since_last_action()
        assert len(since_action) == 1
        assert since_action[0] is new_event

    def test_count_by_type(self) -> None:
        """Test count_by_type returns correct counts."""
        ctx = DecisionContext()

        ctx.add(WebSocketEvent(source="test", connection_id="1", content="1"))
        ctx.add(WebSocketEvent(source="test", connection_id="1", content="2"))
        ctx.add(HTTPEvent(source="test", method="GET", path="/"))
        ctx.add(TimerEvent(source="test", timer_name="tick"))
        ctx.add(TimerEvent(source="test", timer_name="tick"))
        ctx.add(TimerEvent(source="test", timer_name="tick"))

        counts = ctx.count_by_type()
        assert counts["ws.message"] == 2
        assert counts["http.request"] == 1
        assert counts["timer.tick"] == 3

    def test_summarize_returns_string(self) -> None:
        """Test summarize returns a formatted string."""
        ctx = DecisionContext()

        ctx.add(WebSocketEvent(source="ws:client1", connection_id="1", content="hi"))
        ctx.add(HTTPEvent(source="http:api", method="POST", path="/events"))

        summary = ctx.summarize()

        assert isinstance(summary, str)
        assert "2 total events" in summary
        assert "ws.message" in summary
        assert "http.request" in summary

    def test_summarize_max_events(self) -> None:
        """Test summarize respects max_events parameter."""
        ctx = DecisionContext()

        # Add 15 events
        for i in range(15):
            ctx.add(WebSocketEvent(source="test", connection_id="1", content=f"msg{i}"))

        summary = ctx.summarize(max_events=5)
        # Should only include last 5 events in recent section
        assert "15 total events" in summary

    def test_clear_resets_context(self) -> None:
        """Test clear empties events and sets last_action_time."""
        ctx = DecisionContext()

        ctx.add(WebSocketEvent(source="test", connection_id="1", content="hi"))
        ctx.add(WebSocketEvent(source="test", connection_id="1", content="bye"))

        ctx.clear()

        assert ctx.events == []
        assert ctx.last_action_time is not None

    def test_mark_action_sets_time_without_clear(self) -> None:
        """Test mark_action sets time but keeps events."""
        ctx = DecisionContext()

        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        ctx.add(event)

        assert ctx.last_action_time is None
        ctx.mark_action()

        assert ctx.last_action_time is not None
        assert len(ctx.events) == 1
        assert ctx.events[0] is event
