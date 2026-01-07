"""Tests for agent context."""

from unittest.mock import AsyncMock

from reflex.core.context import AgentContext
from reflex.core.events import EventMeta, WebSocketEvent


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
