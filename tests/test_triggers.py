"""Tests for trigger system."""

from reflex.agent.base import SimpleAgent
from reflex.agent.filters import TypeFilter
from reflex.agent.triggers import Trigger, TriggerRegistry
from reflex.core.context import AgentContext
from reflex.core.events import WebSocketEvent


class DummyAgent(SimpleAgent):
    """Dummy agent for testing."""

    async def handle(self, ctx: AgentContext) -> None:
        pass


class TestTrigger:
    """Tests for Trigger class."""

    def test_matches_delegates_to_filter(self) -> None:
        """Test that trigger.matches delegates to filter."""
        trigger = Trigger(
            name="test",
            filter=TypeFilter(types=["ws.message"]),
            agent=DummyAgent(),
        )

        ws_event = WebSocketEvent(source="test", connection_id="1", content="hi")
        assert trigger.matches(ws_event)

    def test_default_scope_key(self) -> None:
        """Test default scope_key uses event source."""
        trigger = Trigger(
            name="test",
            filter=TypeFilter(types=["ws.message"]),
            agent=DummyAgent(),
        )

        event = WebSocketEvent(source="ws:client-123", connection_id="1", content="hi")
        assert trigger.get_scope(event) == "ws:client-123"

    def test_custom_scope_key(self) -> None:
        """Test custom scope_key function."""
        trigger = Trigger(
            name="test",
            filter=TypeFilter(types=["ws.message"]),
            agent=DummyAgent(),
            scope_key=lambda e: f"conn:{e.connection_id}",  # type: ignore[attr-defined]
        )

        event = WebSocketEvent(source="ws:client-123", connection_id="conn-456", content="hi")
        assert trigger.get_scope(event) == "conn:conn-456"


class TestTriggerRegistry:
    """Tests for TriggerRegistry."""

    def test_register_and_get(self) -> None:
        """Test registering and retrieving a trigger."""
        registry = TriggerRegistry()
        trigger = Trigger(
            name="test_trigger",
            filter=TypeFilter(types=["ws.message"]),
            agent=DummyAgent(),
        )

        registry.register(trigger)
        assert registry.get("test_trigger") is trigger

    def test_get_nonexistent(self) -> None:
        """Test getting a trigger that doesn't exist."""
        registry = TriggerRegistry()
        assert registry.get("nonexistent") is None

    def test_unregister(self) -> None:
        """Test unregistering a trigger."""
        registry = TriggerRegistry()
        trigger = Trigger(
            name="test_trigger",
            filter=TypeFilter(types=["ws.message"]),
            agent=DummyAgent(),
        )

        registry.register(trigger)
        assert registry.unregister("test_trigger") is True
        assert registry.get("test_trigger") is None

    def test_unregister_nonexistent(self) -> None:
        """Test unregistering a trigger that doesn't exist."""
        registry = TriggerRegistry()
        assert registry.unregister("nonexistent") is False

    def test_match_single_trigger(self) -> None:
        """Test matching a single trigger."""
        registry = TriggerRegistry()
        trigger = Trigger(
            name="ws_handler",
            filter=TypeFilter(types=["ws.message"]),
            agent=DummyAgent(),
        )
        registry.register(trigger)

        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        matches = registry.match(event)

        assert len(matches) == 1
        assert matches[0] is trigger

    def test_match_multiple_triggers(self) -> None:
        """Test matching multiple triggers."""
        registry = TriggerRegistry()

        trigger1 = Trigger(
            name="handler1",
            filter=TypeFilter(types=["ws.message"]),
            agent=DummyAgent(),
        )
        trigger2 = Trigger(
            name="handler2",
            filter=TypeFilter(types=["ws.message"]),
            agent=DummyAgent(),
        )
        trigger3 = Trigger(
            name="handler3",
            filter=TypeFilter(types=["http.request"]),
            agent=DummyAgent(),
        )

        registry.register(trigger1)
        registry.register(trigger2)
        registry.register(trigger3)

        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        matches = registry.match(event)

        assert len(matches) == 2
        assert trigger1 in matches
        assert trigger2 in matches
        assert trigger3 not in matches

    def test_match_respects_priority(self) -> None:
        """Test that matches are returned in priority order."""
        registry = TriggerRegistry()

        low_priority = Trigger(
            name="low",
            filter=TypeFilter(types=["ws.message"]),
            agent=DummyAgent(),
            priority=1,
        )
        high_priority = Trigger(
            name="high",
            filter=TypeFilter(types=["ws.message"]),
            agent=DummyAgent(),
            priority=10,
        )
        medium_priority = Trigger(
            name="medium",
            filter=TypeFilter(types=["ws.message"]),
            agent=DummyAgent(),
            priority=5,
        )

        # Register in random order
        registry.register(low_priority)
        registry.register(high_priority)
        registry.register(medium_priority)

        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        matches = registry.match(event)

        assert len(matches) == 3
        assert matches[0] is high_priority
        assert matches[1] is medium_priority
        assert matches[2] is low_priority

    def test_triggers_property(self) -> None:
        """Test triggers property returns all triggers."""
        registry = TriggerRegistry()

        trigger1 = Trigger(
            name="t1",
            filter=TypeFilter(types=["ws.message"]),
            agent=DummyAgent(),
        )
        trigger2 = Trigger(
            name="t2",
            filter=TypeFilter(types=["http.request"]),
            agent=DummyAgent(),
        )

        registry.register(trigger1)
        registry.register(trigger2)

        triggers = registry.triggers
        assert len(triggers) == 2
        assert trigger1 in triggers
        assert trigger2 in triggers

    def test_clear(self) -> None:
        """Test clearing all triggers."""
        registry = TriggerRegistry()

        registry.register(
            Trigger(
                name="t1",
                filter=TypeFilter(types=["ws.message"]),
                agent=DummyAgent(),
            )
        )
        registry.register(
            Trigger(
                name="t2",
                filter=TypeFilter(types=["http.request"]),
                agent=DummyAgent(),
            )
        )

        registry.clear()
        assert len(registry.triggers) == 0
