"""Tests for trigger functions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from reflex.agent.triggers import (
    error_threshold_trigger,
    immediate_trigger,
    periodic_summary_trigger,
)
from reflex.core.context import DecisionContext
from reflex.core.deps import ReflexDeps
from reflex.core.events import LifecycleEvent, WebSocketEvent


@pytest.fixture
def mock_deps() -> ReflexDeps:
    """Create mock dependencies."""
    return ReflexDeps(
        store=AsyncMock(),
        http=MagicMock(),
        db=AsyncMock(),
        scope="test",
    )


class TestErrorThresholdTrigger:
    """Tests for error_threshold_trigger."""

    @pytest.mark.asyncio
    async def test_no_trigger_below_threshold(self, mock_deps: ReflexDeps) -> None:
        """Test trigger doesn't fire below threshold."""
        ctx = DecisionContext()
        trigger = error_threshold_trigger(threshold=5, window_seconds=60)

        # Add only 3 lifecycle events
        for i in range(3):
            event = LifecycleEvent(source="test", action="error", details=f"error {i}")
            ctx.add(event)

        result = await trigger(ctx, mock_deps)
        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_at_threshold(self, mock_deps: ReflexDeps) -> None:
        """Test trigger fires at threshold."""
        ctx = DecisionContext()
        trigger = error_threshold_trigger(threshold=5, window_seconds=60)

        # Add 5 lifecycle events
        for i in range(5):
            event = LifecycleEvent(source="test", action="error", details=f"error {i}")
            ctx.add(event)

        result = await trigger(ctx, mock_deps)
        assert result is not None
        assert result["triggered"] is True
        assert result["error_count"] == 5

    @pytest.mark.asyncio
    async def test_trigger_respects_error_types(self, mock_deps: ReflexDeps) -> None:
        """Test trigger only counts specified error types."""
        ctx = DecisionContext()
        trigger = error_threshold_trigger(
            threshold=3, window_seconds=60, error_types=("lifecycle",)
        )

        # Add 2 lifecycle events and 5 websocket events
        for i in range(2):
            ctx.add(LifecycleEvent(source="test", action="error", details=f"error {i}"))
        for i in range(5):
            ctx.add(WebSocketEvent(source="test", connection_id="1", content=f"msg {i}"))

        result = await trigger(ctx, mock_deps)
        assert result is None  # Only 2 lifecycle events, below threshold

    @pytest.mark.asyncio
    async def test_trigger_respects_window(self, mock_deps: ReflexDeps) -> None:
        """Test trigger only counts events in window."""
        ctx = DecisionContext()
        trigger = error_threshold_trigger(threshold=3, window_seconds=60)
        now = datetime.now(UTC)

        # Add 2 old events outside window
        for i in range(2):
            event = LifecycleEvent(
                source="test",
                action="error",
                details=f"old {i}",
                timestamp=now - timedelta(seconds=120),
            )
            ctx.add(event)

        # Add 2 recent events in window
        for i in range(2):
            event = LifecycleEvent(
                source="test",
                action="error",
                details=f"recent {i}",
                timestamp=now,
            )
            ctx.add(event)

        result = await trigger(ctx, mock_deps)
        assert result is None  # Only 2 events in window


class TestPeriodicSummaryTrigger:
    """Tests for periodic_summary_trigger."""

    @pytest.mark.asyncio
    async def test_no_trigger_below_count(self, mock_deps: ReflexDeps) -> None:
        """Test trigger doesn't fire below event count."""
        ctx = DecisionContext()
        trigger = periodic_summary_trigger(event_count=10)

        # Add only 5 events
        for i in range(5):
            ctx.add(WebSocketEvent(source="test", connection_id="1", content=f"msg {i}"))

        result = await trigger(ctx, mock_deps)
        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_at_count(self, mock_deps: ReflexDeps) -> None:
        """Test trigger fires at event count."""
        ctx = DecisionContext()
        trigger = periodic_summary_trigger(event_count=10)

        # Add 10 events
        for i in range(10):
            ctx.add(WebSocketEvent(source="test", connection_id="1", content=f"msg {i}"))

        result = await trigger(ctx, mock_deps)
        assert result is not None
        assert result["triggered"] is True
        assert result["event_count"] == 10

    @pytest.mark.asyncio
    async def test_trigger_clears_context(self, mock_deps: ReflexDeps) -> None:
        """Test trigger clears context after firing."""
        ctx = DecisionContext()
        trigger = periodic_summary_trigger(event_count=5)

        # Add 5 events
        for i in range(5):
            ctx.add(WebSocketEvent(source="test", connection_id="1", content=f"msg {i}"))

        await trigger(ctx, mock_deps)
        assert len(ctx.events) == 0

    @pytest.mark.asyncio
    async def test_trigger_respects_since_last_action(self, mock_deps: ReflexDeps) -> None:
        """Test trigger only counts events since last action."""
        ctx = DecisionContext()
        trigger = periodic_summary_trigger(event_count=5)
        now = datetime.now(UTC)

        # Add 3 old events
        for i in range(3):
            ctx.add(
                WebSocketEvent(
                    source="test",
                    connection_id="1",
                    content=f"old {i}",
                    timestamp=now - timedelta(seconds=10),
                )
            )

        # Mark action
        ctx.mark_action()

        # Add 3 new events (not enough)
        for i in range(3):
            ctx.add(
                WebSocketEvent(
                    source="test",
                    connection_id="1",
                    content=f"new {i}",
                    timestamp=now + timedelta(seconds=1),
                )
            )

        result = await trigger(ctx, mock_deps)
        assert result is None  # Only 3 events since action


class TestImmediateTrigger:
    """Tests for immediate_trigger."""

    @pytest.mark.asyncio
    async def test_always_fires(self, mock_deps: ReflexDeps) -> None:
        """Test immediate trigger always fires."""
        ctx = DecisionContext()
        trigger = immediate_trigger()

        ctx.add(WebSocketEvent(source="test", connection_id="1", content="hi"))

        result = await trigger(ctx, mock_deps)
        assert result is not None
        assert result["triggered"] is True

    @pytest.mark.asyncio
    async def test_includes_event_count(self, mock_deps: ReflexDeps) -> None:
        """Test immediate trigger includes event count."""
        ctx = DecisionContext()
        trigger = immediate_trigger()

        for i in range(3):
            ctx.add(WebSocketEvent(source="test", connection_id="1", content=f"msg {i}"))

        result = await trigger(ctx, mock_deps)
        assert result is not None
        assert result["event_count"] == 3

    @pytest.mark.asyncio
    async def test_includes_latest_event(self, mock_deps: ReflexDeps) -> None:
        """Test immediate trigger includes latest event."""
        ctx = DecisionContext()
        trigger = immediate_trigger()

        last_event = WebSocketEvent(source="test", connection_id="1", content="last")
        ctx.add(WebSocketEvent(source="test", connection_id="1", content="first"))
        ctx.add(last_event)

        result = await trigger(ctx, mock_deps)
        assert result is not None
        assert result["latest_event"] is last_event

    @pytest.mark.asyncio
    async def test_marks_action(self, mock_deps: ReflexDeps) -> None:
        """Test immediate trigger marks action."""
        ctx = DecisionContext()
        trigger = immediate_trigger()

        ctx.add(WebSocketEvent(source="test", connection_id="1", content="hi"))

        assert ctx.last_action_time is None
        await trigger(ctx, mock_deps)
        assert ctx.last_action_time is not None
