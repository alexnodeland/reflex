"""Event store with persistence, replay, and acknowledgment."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Protocol

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from reflex.events import Event


class EventStore(Protocol):
    """Protocol for event stores."""

    async def publish(self, event: Event) -> None:
        """Store an event."""
        ...

    async def subscribe(
        self,
        event_types: list[str] | None = None,
    ) -> AsyncIterator[tuple[Event, str]]:
        """Yield (event, ack_token) pairs. Call ack() or nack() with token."""
        ...

    async def ack(self, token: str) -> None:
        """Mark event as processed."""
        ...

    async def nack(self, token: str, error: str | None = None) -> None:
        """Mark event as failed. Will retry up to max_attempts."""
        ...

    async def replay(
        self,
        start: datetime,
        end: datetime | None = None,
        event_types: list[str] | None = None,
    ) -> AsyncIterator[Event]:
        """Replay historical events for debugging."""
        ...


class EventRecord(SQLModel, table=True):
    """Database model for events."""

    __tablename__ = "events"  # type: ignore[assignment]

    id: str = SQLField(primary_key=True)
    type: str = SQLField(index=True)
    source: str
    timestamp: datetime = SQLField(index=True)
    payload: str  # JSON
    status: str = SQLField(default="pending", index=True)
    attempts: int = SQLField(default=0)
    error: str | None = None


class SQLiteEventStore:
    """SQLite-backed event store with async sessions."""

    def __init__(self, db_url: str = "sqlite+aiosqlite:///reflex.db"):
        self.engine = create_async_engine(db_url)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self.max_attempts = 3
        self._event_adapter: TypeAdapter[Event] = TypeAdapter(Event)
        self._notify = asyncio.Event()

    async def init(self) -> None:
        """Initialize the database schema."""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def close(self) -> None:
        """Close the database connection."""
        await self.engine.dispose()

    async def publish(self, event: Event) -> None:
        """Store an event."""
        async with self.session_factory() as session:
            record = EventRecord(
                id=event.id,
                type=event.type,
                source=event.source,
                timestamp=event.timestamp,
                payload=event.model_dump_json(),
            )
            session.add(record)
            await session.commit()
        self._notify.set()  # Wake up subscribers

    async def subscribe(
        self,
        event_types: list[str] | None = None,
    ) -> AsyncIterator[tuple[Event, str]]:
        """Yield (event, ack_token) pairs. Call ack() or nack() with token."""
        while True:
            async with self.session_factory() as session:
                query = (
                    select(EventRecord)
                    .where(EventRecord.status == "pending")
                    .order_by(EventRecord.timestamp)
                    .limit(100)
                )
                if event_types:
                    query = query.where(EventRecord.type.in_(event_types))

                result = await session.exec(query)
                records = list(result.all())

                for record in records:
                    record.status = "processing"
                    record.attempts += 1
                    session.add(record)
                    await session.commit()

                    event = self._event_adapter.validate_json(record.payload)
                    yield event, record.id

            if not records:
                self._notify.clear()
                try:
                    await asyncio.wait_for(self._notify.wait(), timeout=1.0)
                except TimeoutError:
                    pass

    async def ack(self, token: str) -> None:
        """Mark event as processed."""
        async with self.session_factory() as session:
            record = await session.get(EventRecord, token)
            if record:
                record.status = "completed"
                session.add(record)
                await session.commit()

    async def nack(self, token: str, error: str | None = None) -> None:
        """Mark event as failed. Will retry up to max_attempts."""
        async with self.session_factory() as session:
            record = await session.get(EventRecord, token)
            if record:
                record.error = error
                if record.attempts >= self.max_attempts:
                    record.status = "dlq"
                else:
                    record.status = "pending"
                session.add(record)
                await session.commit()

    async def replay(
        self,
        start: datetime,
        end: datetime | None = None,
        event_types: list[str] | None = None,
    ) -> AsyncIterator[Event]:
        """Replay historical events for debugging."""
        async with self.session_factory() as session:
            query = select(EventRecord).where(EventRecord.timestamp >= start)

            if end is not None:
                query = query.where(EventRecord.timestamp <= end)

            if event_types:
                query = query.where(EventRecord.type.in_(event_types))

            query = query.order_by(EventRecord.timestamp)

            result = await session.exec(query)
            for record in result.all():
                yield self._event_adapter.validate_json(record.payload)

    async def get_dlq_events(self) -> AsyncIterator[Event]:
        """Retrieve events in the dead letter queue."""
        async with self.session_factory() as session:
            query = (
                select(EventRecord)
                .where(EventRecord.status == "dlq")
                .order_by(EventRecord.timestamp)
            )

            result = await session.exec(query)
            for record in result.all():
                yield self._event_adapter.validate_json(record.payload)
