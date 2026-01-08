"""Integration tests for EventStore.

These tests require a running PostgreSQL database.
They are automatically skipped if DATABASE_URL is not set.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from reflex.core.events import LifecycleEvent, WebSocketEvent

if TYPE_CHECKING:
    from reflex.infra.store import EventStore


@pytest.mark.asyncio
class TestEventStorePublish:
    """Tests for EventStore.publish()."""

    async def test_publish_event(self, store: EventStore) -> None:
        """Test publishing an event persists it to the database."""
        event = WebSocketEvent(
            source="test-client",
            connection_id="conn-123",
            content="Hello, World!",
        )

        await store.publish(event)

        # Verify event was persisted
        async with store.session_factory() as session:
            from sqlalchemy import text

            result = await session.execute(  # pyright: ignore[reportDeprecated]
                text("SELECT id, type, source, status FROM events WHERE id = :id"),
                {"id": event.id},
            )
            row = result.fetchone()
            assert row is not None
            assert row.id == event.id
            assert row.type == "ws.message"
            assert row.source == "test-client"
            assert row.status == "pending"

    async def test_publish_multiple_events(self, store: EventStore) -> None:
        """Test publishing multiple events."""
        events = [
            WebSocketEvent(source="client-1", connection_id="c1", content=f"msg-{i}")
            for i in range(5)
        ]

        for event in events:
            await store.publish(event)

        # Verify all events persisted
        async with store.session_factory() as session:
            from sqlalchemy import text

            result = await session.execute(  # pyright: ignore[reportDeprecated]
                text("SELECT COUNT(*) FROM events WHERE source LIKE 'client-%'")
            )
            count = result.scalar()
            assert count == 5


@pytest.mark.asyncio
class TestEventStoreAckNack:
    """Tests for EventStore.ack() and nack()."""

    async def test_ack_marks_completed(self, store: EventStore) -> None:
        """Test ack() marks event as completed."""
        event = WebSocketEvent(source="test", connection_id="c1", content="test")
        await store.publish(event)

        # Mark as processing first (simulating subscribe)
        async with store.session_factory() as session:
            from sqlalchemy import text

            await session.execute(  # pyright: ignore[reportDeprecated]
                text("UPDATE events SET status = 'processing' WHERE id = :id"),
                {"id": event.id},
            )
            await session.commit()

        # Ack the event
        await store.ack(event.id)

        # Verify status
        async with store.session_factory() as session:
            from sqlalchemy import text

            result = await session.execute(  # pyright: ignore[reportDeprecated]
                text("SELECT status, processed_at FROM events WHERE id = :id"),
                {"id": event.id},
            )
            row = result.fetchone()
            assert row is not None
            assert row.status == "completed"
            assert row.processed_at is not None

    async def test_nack_retries_event(self, store: EventStore) -> None:
        """Test nack() returns event to pending for retry."""
        event = WebSocketEvent(source="test", connection_id="c1", content="test")
        await store.publish(event)

        # Set as processing with 1 attempt (below max)
        async with store.session_factory() as session:
            from sqlalchemy import text

            await session.execute(  # pyright: ignore[reportDeprecated]
                text("UPDATE events SET status = 'processing', attempts = 1 WHERE id = :id"),
                {"id": event.id},
            )
            await session.commit()

        # Nack the event
        await store.nack(event.id, error="Test error")

        # Verify status is back to pending
        async with store.session_factory() as session:
            from sqlalchemy import text

            result = await session.execute(  # pyright: ignore[reportDeprecated]
                text("SELECT status, error FROM events WHERE id = :id"),
                {"id": event.id},
            )
            row = result.fetchone()
            assert row is not None
            assert row.status == "pending"
            assert row.error == "Test error"

    async def test_nack_moves_to_dlq_after_max_attempts(self, store: EventStore) -> None:
        """Test nack() moves event to DLQ after max attempts."""
        event = WebSocketEvent(source="test", connection_id="c1", content="test")
        await store.publish(event)

        # Set as processing with max attempts
        async with store.session_factory() as session:
            from sqlalchemy import text

            await session.execute(  # pyright: ignore[reportDeprecated]
                text("UPDATE events SET status = 'processing', attempts = :max WHERE id = :id"),
                {"id": event.id, "max": store.max_attempts},
            )
            await session.commit()

        # Nack the event
        await store.nack(event.id, error="Final failure")

        # Verify status is dlq
        async with store.session_factory() as session:
            from sqlalchemy import text

            result = await session.execute(  # pyright: ignore[reportDeprecated]
                text("SELECT status FROM events WHERE id = :id"),
                {"id": event.id},
            )
            row = result.fetchone()
            assert row is not None
            assert row.status == "dlq"


@pytest.mark.asyncio
class TestEventStoreDLQ:
    """Tests for DLQ management."""

    async def test_dlq_list_returns_dlq_events(self, store: EventStore) -> None:
        """Test dlq_list() returns events in DLQ."""
        # Create events and move them to DLQ
        dlq_events_to_create = [
            LifecycleEvent(source="test", action="error", details=f"error-{i}") for i in range(3)
        ]

        for event in dlq_events_to_create:
            await store.publish(event)
            async with store.session_factory() as session:
                from sqlalchemy import text

                await session.execute(  # pyright: ignore[reportDeprecated]
                    text("UPDATE events SET status = 'dlq' WHERE id = :id"),
                    {"id": event.id},
                )
                await session.commit()

        # List DLQ
        dlq_events = await store.dlq_list(limit=10)
        assert len(dlq_events) >= 3

    async def test_dlq_retry_moves_to_pending(self, store: EventStore) -> None:
        """Test dlq_retry() moves event back to pending."""
        event = LifecycleEvent(source="test", action="error", details="error")
        await store.publish(event)

        # Move to DLQ
        async with store.session_factory() as session:
            from sqlalchemy import text

            await session.execute(  # pyright: ignore[reportDeprecated]
                text("UPDATE events SET status = 'dlq', attempts = 3 WHERE id = :id"),
                {"id": event.id},
            )
            await session.commit()

        # Retry
        success = await store.dlq_retry(event.id)
        assert success is True

        # Verify status
        async with store.session_factory() as session:
            from sqlalchemy import text

            result = await session.execute(  # pyright: ignore[reportDeprecated]
                text("SELECT status, attempts FROM events WHERE id = :id"),
                {"id": event.id},
            )
            row = result.fetchone()
            assert row is not None
            assert row.status == "pending"
            assert row.attempts == 0

    async def test_dlq_retry_returns_false_for_nonexistent(self, store: EventStore) -> None:
        """Test dlq_retry() returns False for non-existent event."""
        success = await store.dlq_retry("nonexistent-id")
        assert success is False


@pytest.mark.asyncio
class TestEventStoreReplay:
    """Tests for EventStore.replay()."""

    async def test_replay_returns_events_in_range(self, store: EventStore) -> None:
        """Test replay() returns events within time range."""
        now = datetime.now(UTC)

        # Create events at different times
        old_event = WebSocketEvent(
            source="test",
            connection_id="c1",
            content="old",
            timestamp=now - timedelta(hours=2),
        )
        recent_event = WebSocketEvent(
            source="test",
            connection_id="c1",
            content="recent",
            timestamp=now - timedelta(minutes=30),
        )

        await store.publish(old_event)
        await store.publish(recent_event)

        # Replay last hour
        replayed_events: list[Any] = []
        async for event in store.replay(start=now - timedelta(hours=1)):
            replayed_events.append(event)

        # Should only get recent event
        assert len(replayed_events) == 1
        assert replayed_events[0].id == recent_event.id

    async def test_replay_filters_by_type(self, store: EventStore) -> None:
        """Test replay() filters by event type."""
        now = datetime.now(UTC)

        ws_event = WebSocketEvent(source="test", connection_id="c1", content="ws", timestamp=now)
        lifecycle_event = LifecycleEvent(
            source="test", action="started", details="started", timestamp=now
        )

        await store.publish(ws_event)
        await store.publish(lifecycle_event)

        # Replay only lifecycle events
        filtered_events: list[Any] = []
        async for event in store.replay(
            start=now - timedelta(minutes=1),
            event_types=["lifecycle"],
        ):
            filtered_events.append(event)

        assert len(filtered_events) == 1
        assert filtered_events[0].id == lifecycle_event.id
