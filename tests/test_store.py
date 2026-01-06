"""Tests for event store."""

import asyncio
from datetime import datetime

import pytest

from reflex.events import FileEvent, HTTPEvent, TimerEvent, WebSocketEvent
from reflex.store import SQLiteEventStore


@pytest.fixture
async def store() -> SQLiteEventStore:
    """Create a fresh in-memory event store for each test."""
    store = SQLiteEventStore(db_url="sqlite+aiosqlite:///:memory:")
    await store.init()
    yield store
    await store.close()


class TestSQLiteEventStore:
    """Tests for SQLiteEventStore."""

    async def test_init(self, store: SQLiteEventStore) -> None:
        """Should initialize database schema."""
        # Store fixture already calls init(), so just verify it works
        assert store.engine is not None

    async def test_publish_and_subscribe(self, store: SQLiteEventStore) -> None:
        """Should publish and receive events."""
        event = WebSocketEvent(
            source="test",
            connection_id="conn-1",
            content="hello",
        )
        await store.publish(event)

        async for received, token in store.subscribe():
            assert received.id == event.id
            assert isinstance(received, WebSocketEvent)
            assert received.content == "hello"
            await store.ack(token)
            break

    async def test_publish_multiple_events(self, store: SQLiteEventStore) -> None:
        """Should handle multiple events in order."""
        events = [
            WebSocketEvent(source="test", connection_id="c1", content="first"),
            WebSocketEvent(source="test", connection_id="c2", content="second"),
            WebSocketEvent(source="test", connection_id="c3", content="third"),
        ]

        for event in events:
            await store.publish(event)

        received_events = []
        async for event, token in store.subscribe():
            received_events.append(event)
            await store.ack(token)
            if len(received_events) == 3:
                break

        assert len(received_events) == 3
        for i, received in enumerate(received_events):
            assert isinstance(received, WebSocketEvent)
            assert received.id == events[i].id

    async def test_subscribe_with_event_types_filter(self, store: SQLiteEventStore) -> None:
        """Should filter events by type."""
        ws_event = WebSocketEvent(source="test", connection_id="c1", content="hello")
        http_event = HTTPEvent(source="test", method="GET", path="/api")

        await store.publish(ws_event)
        await store.publish(http_event)

        # Subscribe only to HTTP events
        received = []
        async for event, token in store.subscribe(event_types=["http.request"]):
            received.append(event)
            await store.ack(token)
            break

        assert len(received) == 1
        assert isinstance(received[0], HTTPEvent)

    async def test_ack_marks_completed(self, store: SQLiteEventStore) -> None:
        """Should mark event as completed after ack."""
        event = WebSocketEvent(source="test", connection_id="c1", content="hi")
        await store.publish(event)

        # First subscribe and ack
        async for _, token in store.subscribe():
            await store.ack(token)
            break

        # Subscribe again - should not get the same event
        received = []
        timeout_task = asyncio.create_task(asyncio.sleep(0.5))

        async def collect() -> None:
            async for ev, tok in store.subscribe():
                received.append(ev)
                await store.ack(tok)

        collector = asyncio.create_task(collect())

        await timeout_task
        collector.cancel()
        try:
            await collector
        except asyncio.CancelledError:
            pass

        assert len(received) == 0

    async def test_nack_retries(self, store: SQLiteEventStore) -> None:
        """Should retry events after nack."""
        event = WebSocketEvent(source="test", connection_id="c1", content="hi")
        await store.publish(event)

        # First attempt - nack
        async for _, token in store.subscribe():
            await store.nack(token, "test error")
            break

        # Second attempt - should get same event
        async for received, token in store.subscribe():
            assert received.id == event.id
            await store.ack(token)
            break

    async def test_nack_dlq_after_max_attempts(self, store: SQLiteEventStore) -> None:
        """Should move to DLQ after max attempts."""
        store.max_attempts = 2  # Lower for testing
        event = WebSocketEvent(source="test", connection_id="c1", content="hi")
        await store.publish(event)

        # Exhaust attempts
        for _ in range(2):
            async for _, token in store.subscribe():
                await store.nack(token, "test error")
                break

        # Should not receive event again (it's in DLQ)
        received_any = False
        timeout_task = asyncio.create_task(asyncio.sleep(0.5))

        async def collect() -> None:
            nonlocal received_any
            async for _, tok in store.subscribe():
                received_any = True
                await store.ack(tok)

        collector = asyncio.create_task(collect())

        await timeout_task
        collector.cancel()
        try:
            await collector
        except asyncio.CancelledError:
            pass

        assert not received_any

    async def test_replay(self, store: SQLiteEventStore) -> None:
        """Should replay historical events."""
        start = datetime.utcnow()

        events = [
            WebSocketEvent(source="test", connection_id="c1", content="first"),
            WebSocketEvent(source="test", connection_id="c2", content="second"),
        ]

        for event in events:
            await store.publish(event)

        # Replay all events
        replayed = []
        async for event in store.replay(start=start):
            replayed.append(event)

        assert len(replayed) == 2

    async def test_replay_with_time_range(self, store: SQLiteEventStore) -> None:
        """Should replay events within time range."""
        event1 = WebSocketEvent(source="test", connection_id="c1", content="old")
        await store.publish(event1)

        await asyncio.sleep(0.1)
        mid = datetime.utcnow()
        await asyncio.sleep(0.1)

        event2 = WebSocketEvent(source="test", connection_id="c2", content="new")
        await store.publish(event2)

        # Replay only newer events
        replayed = []
        async for event in store.replay(start=mid):
            replayed.append(event)

        assert len(replayed) == 1
        assert isinstance(replayed[0], WebSocketEvent)
        assert replayed[0].content == "new"

    async def test_replay_with_event_types(self, store: SQLiteEventStore) -> None:
        """Should replay only specified event types."""
        start = datetime.utcnow()

        ws_event = WebSocketEvent(source="test", connection_id="c1", content="ws")
        http_event = HTTPEvent(source="test", method="GET", path="/api")

        await store.publish(ws_event)
        await store.publish(http_event)

        # Replay only HTTP events
        replayed = []
        async for event in store.replay(start=start, event_types=["http.request"]):
            replayed.append(event)

        assert len(replayed) == 1
        assert isinstance(replayed[0], HTTPEvent)

    async def test_get_dlq_events(self, store: SQLiteEventStore) -> None:
        """Should retrieve DLQ events."""
        store.max_attempts = 1

        event = WebSocketEvent(source="test", connection_id="c1", content="fail")
        await store.publish(event)

        # Exhaust attempts
        async for _, token in store.subscribe():
            await store.nack(token, "error")
            break

        # Check DLQ
        dlq_events = []
        async for ev in store.get_dlq_events():
            dlq_events.append(ev)

        assert len(dlq_events) == 1
        assert dlq_events[0].id == event.id

    async def test_notify_wakes_subscriber(self, store: SQLiteEventStore) -> None:
        """Publishing should wake up waiting subscribers."""
        event = WebSocketEvent(source="test", connection_id="c1", content="hi")

        received_event = None

        async def subscribe_task() -> None:
            nonlocal received_event
            async for ev, token in store.subscribe():
                received_event = ev
                await store.ack(token)
                break

        # Start subscriber
        task = asyncio.create_task(subscribe_task())

        # Give subscriber time to start waiting
        await asyncio.sleep(0.1)

        # Publish - should wake subscriber
        await store.publish(event)

        # Wait for subscriber to finish
        await asyncio.wait_for(task, timeout=2.0)

        assert received_event is not None
        assert received_event.id == event.id

    async def test_multiple_event_types(self, store: SQLiteEventStore) -> None:
        """Should handle all event types correctly."""
        events = [
            WebSocketEvent(source="ws", connection_id="c1", content="hello"),
            HTTPEvent(source="http", method="POST", path="/api", body={"key": "value"}),
            FileEvent(source="fs", path="/tmp/test.txt", change_type="created"),
            TimerEvent(source="timer", timer_name="heartbeat"),
        ]

        for event in events:
            await store.publish(event)

        received = []
        async for event, token in store.subscribe():
            received.append(event)
            await store.ack(token)
            if len(received) == 4:
                break

        assert len(received) == 4
        assert isinstance(received[0], WebSocketEvent)
        assert isinstance(received[1], HTTPEvent)
        assert isinstance(received[2], FileEvent)
        assert isinstance(received[3], TimerEvent)
