# Reflex

## Product Requirements Document

**Version:** 0.5.0  
**Status:** Draft  
**Author:** Alex Nodeland  
**Date:** January 2026

-----

## Executive Summary

Reflex is a template project for building real-time AI agents as continuous control systems. Clone it, run `docker compose up`, and start building. It provides production-ready infrastructure—event storage with Postgres, observability via Logfire, async API layer—with clean architecture meant to be modified, not imported.

```bash
git clone https://github.com/yourorg/reflex my-agent
cd my-agent
cp .env.example .env
docker compose up
```

Your agent is running. Now rip out the example and build your own.

The core insight: agents should behave like control systems with closed perception-action loops, not request-response handlers that wake up, think, and sleep. Reflex provides the architectural primitives—event sourcing, context accumulation, typed triggers—while staying true to the “it’s just Python” philosophy of the Pydantic ecosystem.

-----

## What You Get

**Infrastructure (keep this):**

- Docker Compose with hot reload
- PostgreSQL with async access and LISTEN/NOTIFY
- Logfire observability (pre-configured for full-stack tracing)
- FastAPI with WebSocket support and proper lifecycle management
- Health checks and graceful shutdown
- CI/CD templates (GitHub Actions)
- Test setup with pytest-asyncio
- Replay and debugging utilities

**Example Agent (replace this):**

- Event types with discriminated unions
- EventStore with persistence, replay, DLQ
- Decision context (working memory)
- Sample filters and triggers
- PydanticAI agent with tools

-----

## Design Philosophy

**Fork and own.** This isn’t a library with updates to track. Fork it, it’s yours.

**Rip and replace.** The example agent is meant to be deleted. The infrastructure is meant to stay.

**It’s just Python.** No DSLs, no magic combinators, no framework abstractions. Standard async patterns throughout. Following PydanticAI’s philosophy: if you know async Python, you know Reflex.

**Type hints as source of truth.** Types drive validation, serialization, documentation, and IDE support. If it type-checks, it should work.

**Async-first, blocking-never.** Every I/O operation is async. No `time.sleep()`, no `requests.get()`, no lazy-loaded relationships.

**Observability from day one.** Logfire instrumentation is not optional—it’s how you understand what your system is doing.

**Production-ready from day one.** Not a toy that needs hardening—health checks, graceful shutdown, connection pooling, and proper error handling are already there.

-----

## Architecture Overview

### Core Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                         Event Sources                           │
│              (WebSocket, HTTP, Timers, External APIs)           │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                        EVENT STORE                              │
│    PostgreSQL + LISTEN/NOTIFY (Persistence, Replay, DLQ)        │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                        AGENT LOOP                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   Filter    │───▶│   Context   │───▶│   Trigger   │         │
│  │  (fast)     │    │ (accumulate)│    │(PydanticAI) │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
                        ┌───────────────┐
                        │    Effects    │
                        │ (API calls,   │
                        │  messages,    │
                        │  state changes│
                        └───────────────┘
```

### Layer Responsibilities

**Event Sources:** Ingest events from WebSockets, HTTP endpoints, timers, or external systems. Normalize to typed `Event` models using Pydantic discriminated unions. Publish to the event store.

**Event Store:** PostgreSQL-backed persistence with LISTEN/NOTIFY for real-time subscriptions. Handles acknowledgment, retry with backoff, and dead-letter queuing. Supports replay for debugging.

**Agent Loop:** You write this. Subscribes to events, applies filters (fast, no I/O), accumulates into decision context (working memory), evaluates triggers (potentially expensive, may involve LLM calls via PydanticAI).

**Effects:** The actions your triggers produce—API calls, messages, database writes, etc. Executed via PydanticAI agents with typed tools.

-----

## Project Structure

```
reflex/
├── docker/
│   ├── Dockerfile              # Production build
│   ├── Dockerfile.dev          # Development with hot reload
│   └── docker-compose.yml
│
├── src/
│   └── reflex/
│       ├── __init__.py
│       ├── py.typed            # PEP 561 marker for type checking
│       ├── config.py           # Settings from environment
│       │
│       ├── infra/              # KEEP: Infrastructure layer
│       │   ├── __init__.py
│       │   ├── database.py     # Async Postgres setup
│       │   ├── store.py        # EventStore implementation
│       │   ├── locks.py        # Scoped locking utilities
│       │   └── observability.py # Logfire configuration
│       │
│       ├── core/               # MODIFY: Core types
│       │   ├── __init__.py
│       │   ├── events.py       # Event types (discriminated union)
│       │   ├── context.py      # DecisionContext
│       │   └── deps.py         # ReflexDeps
│       │
│       ├── agent/              # REPLACE: Your agent logic
│       │   ├── __init__.py
│       │   ├── filters.py      # Your filter functions
│       │   ├── triggers.py     # Your trigger functions
│       │   ├── agents.py       # Your PydanticAI agents
│       │   └── loop.py         # Your agent loop
│       │
│       └── api/                # MODIFY: API layer
│           ├── __init__.py
│           ├── app.py          # FastAPI application
│           ├── deps.py         # Dependency injection
│           └── routes/
│               ├── __init__.py
│               ├── events.py   # Event ingestion
│               ├── health.py   # Health checks
│               └── ws.py       # WebSocket handlers
│
├── tests/
│   ├── conftest.py             # Fixtures
│   ├── test_store.py
│   ├── test_context.py
│   ├── test_agent.py
│   └── test_api.py
│
├── scripts/
│   ├── migrate.py              # Database migrations
│   └── replay.py               # Event replay utility
│
├── .github/
│   └── workflows/
│       ├── ci.yml              # Lint, type check, test
│       └── deploy.yml          # Build and push image
│
├── .env.example
├── pyproject.toml
├── docker-compose.yml          # Symlink to docker/
├── Makefile                    # Common commands
└── README.md
```

-----

## Technical Design

### Configuration

Settings from environment with Pydantic validation. Follows the twelve-factor app pattern.

```python
# src/reflex/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    # Database
    database_url: str = "postgresql+asyncpg://reflex:reflex@localhost:5432/reflex"
    database_pool_size: int = 5
    database_pool_max_overflow: int = 10
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False
    
    # Observability
    logfire_token: str | None = None
    log_level: str = "INFO"
    
    # Agent
    openai_api_key: str | None = None
    default_model: str = "openai:gpt-4o-mini"
    
    # Event processing
    event_max_attempts: int = 3
    event_retry_base_delay: float = 1.0
    event_retry_max_delay: float = 60.0
    
    # App
    environment: str = "development"
    version: str = "0.1.0"

settings = Settings()
```

-----

### Event System

Events use Pydantic v2 discriminated unions for efficient validation. The discriminator field (`type`) is checked first, avoiding unnecessary validation of non-matching types.

```python
# src/reflex/core/events.py
from pydantic import BaseModel, Field
from typing import Literal, Annotated, Union
from datetime import datetime
from uuid import uuid4

class EventMeta(BaseModel):
    """Trace context for observability.
    
    trace_id: Unique identifier for the trace (propagated through Logfire)
    correlation_id: Links related events across a workflow
    causation_id: The event that directly caused this one
    """
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None
    causation_id: str | None = None

class BaseEvent(BaseModel):
    """Base class for all events.
    
    All events share these fields. The 'type' field is the discriminator
    used for efficient union validation.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(description="Identifier for the event source, e.g., 'ws:client123'")
    meta: EventMeta = Field(default_factory=EventMeta)

# --- Built-in event types ---

class WebSocketEvent(BaseEvent):
    """Event from a WebSocket connection."""
    type: Literal["ws.message"] = "ws.message"
    connection_id: str
    content: str

class HTTPEvent(BaseEvent):
    """Event from an HTTP request."""
    type: Literal["http.request"] = "http.request"
    method: str
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict | None = None

class TimerEvent(BaseEvent):
    """Event from a periodic timer."""
    type: Literal["timer.tick"] = "timer.tick"
    timer_name: str
    tick_count: int = 0

class LifecycleEvent(BaseEvent):
    """Internal lifecycle events."""
    type: Literal["lifecycle"] = "lifecycle"
    action: Literal["started", "stopped", "error"]
    details: str | None = None

# --- Add your event types here ---

# Example custom event:
# class OrderPlacedEvent(BaseEvent):
#     type: Literal["order.placed"] = "order.placed"
#     order_id: str
#     customer_id: str
#     total: float
#     items: list[dict]

# --- Discriminated union of all event types ---
# 
# Add your custom event types to this union.
# The discriminator='type' tells Pydantic to check the 'type' field first,
# making validation O(1) instead of O(n) for the number of event types.

Event = Annotated[
    Union[WebSocketEvent, HTTPEvent, TimerEvent, LifecycleEvent],
    Field(discriminator="type")
]
```

**Extending with custom events:**

```python
# In your own events.py, extend the union:
from reflex.core.events import (
    BaseEvent, WebSocketEvent, HTTPEvent, TimerEvent, LifecycleEvent
)

class OrderPlacedEvent(BaseEvent):
    type: Literal["order.placed"] = "order.placed"
    order_id: str
    customer_id: str
    total: float

class PaymentReceivedEvent(BaseEvent):
    type: Literal["payment.received"] = "payment.received"
    order_id: str
    amount: float
    method: str

# Redefine the union with your types
Event = Annotated[
    Union[
        WebSocketEvent, HTTPEvent, TimerEvent, LifecycleEvent,
        OrderPlacedEvent, PaymentReceivedEvent,
    ],
    Field(discriminator="type")
]
```

-----

### Event Store

PostgreSQL-backed persistence using SQLModel with async sessions. Uses LISTEN/NOTIFY for real-time subscriptions instead of polling.

**Key design decisions:**

- `expire_on_commit=False` on async sessions prevents implicit I/O after commit
- `FOR UPDATE SKIP LOCKED` enables concurrent consumers without conflicts
- LISTEN/NOTIFY wakes subscribers immediately on new events
- Exponential backoff for retries with configurable max attempts
- Dead-letter queue (DLQ) for events that exceed retry limit

```python
# src/reflex/infra/store.py
from sqlmodel import SQLModel, Field as SQLField, text
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from datetime import datetime
from typing import AsyncIterator
from pydantic import TypeAdapter
import asyncio
import asyncpg
import logfire

from reflex.config import settings

class EventRecord(SQLModel, table=True):
    """Persistent event storage.
    
    Status lifecycle:
        pending -> processing -> completed
                            \-> failed (retried) -> pending
                                               \-> dlq (max attempts exceeded)
    """
    __tablename__ = "events"
    
    id: str = SQLField(primary_key=True)
    type: str = SQLField(index=True)
    source: str = SQLField(index=True)
    timestamp: datetime = SQLField(index=True)
    payload: str  # JSON-serialized event
    
    # Processing state
    status: str = SQLField(default="pending", index=True)
    attempts: int = SQLField(default=0)
    error: str | None = SQLField(default=None)
    
    # Timestamps
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    processed_at: datetime | None = SQLField(default=None)

class EventStore:
    """Event persistence with real-time subscriptions.
    
    Uses PostgreSQL LISTEN/NOTIFY for immediate subscriber notification,
    avoiding expensive polling loops.
    """
    
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        pool: asyncpg.Pool,
    ):
        self.session_factory = session_factory
        self.pool = pool
        self.max_attempts = settings.event_max_attempts
        self.retry_base_delay = settings.event_retry_base_delay
        self.retry_max_delay = settings.event_retry_max_delay
    
    async def publish(self, event: "Event") -> None:
        """Persist event and notify subscribers."""
        with logfire.span("store.publish", event_id=event.id, event_type=event.type):
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
            
            # Notify subscribers via LISTEN/NOTIFY
            async with self.pool.acquire() as conn:
                await conn.execute(f"NOTIFY events, '{event.id}'")
            
            logfire.info("Event published", event_id=event.id)
    
    async def subscribe(
        self,
        event_types: list[str] | None = None,
        batch_size: int = 100,
    ) -> AsyncIterator[tuple["Event", str]]:
        """Subscribe to events, yielding (event, ack_token) pairs.
        
        Uses LISTEN/NOTIFY for real-time notification. Subscribers call
        ack() or nack() with the token to mark processing complete.
        
        Events are claimed with FOR UPDATE SKIP LOCKED, allowing multiple
        concurrent consumers without conflicts.
        """
        from reflex.core.events import Event
        adapter = TypeAdapter(Event)
        
        async with self.pool.acquire() as conn:
            # Set up listener
            await conn.execute("LISTEN events")
            
            while True:
                # Claim and fetch pending events
                async with self.session_factory() as session:
                    type_filter = ""
                    if event_types:
                        types_str = ",".join(f"'{t}'" for t in event_types)
                        type_filter = f"AND type IN ({types_str})"
                    
                    query = text(f"""
                        UPDATE events 
                        SET status = 'processing', attempts = attempts + 1
                        WHERE id IN (
                            SELECT id FROM events 
                            WHERE status = 'pending' {type_filter}
                            ORDER BY timestamp
                            LIMIT :batch_size
                            FOR UPDATE SKIP LOCKED
                        )
                        RETURNING id, payload
                    """)
                    
                    result = await session.execute(query, {"batch_size": batch_size})
                    rows = result.fetchall()
                    await session.commit()
                    
                    for row in rows:
                        event = adapter.validate_json(row.payload)
                        yield event, row.id
                
                # If no events, wait for notification
                if not rows:
                    try:
                        await asyncio.wait_for(
                            conn.fetchrow("SELECT 1"),  # Keep connection alive
                            timeout=0.1,
                        )
                        # Wait for NOTIFY
                        notification = await asyncio.wait_for(
                            conn.notifies.get(),
                            timeout=5.0,
                        )
                        logfire.debug("Received notification", event_id=notification.payload)
                    except asyncio.TimeoutError:
                        pass  # Continue loop, check for pending events
    
    async def ack(self, token: str) -> None:
        """Mark event as successfully processed."""
        with logfire.span("store.ack", event_id=token):
            async with self.session_factory() as session:
                await session.execute(
                    text("""
                        UPDATE events 
                        SET status = 'completed', processed_at = NOW() 
                        WHERE id = :id
                    """),
                    {"id": token},
                )
                await session.commit()
    
    async def nack(self, token: str, error: str | None = None) -> None:
        """Mark event as failed.
        
        If attempts < max_attempts, event returns to pending for retry.
        Otherwise, moves to dead-letter queue (status = 'dlq').
        """
        with logfire.span("store.nack", event_id=token, error=error):
            async with self.session_factory() as session:
                await session.execute(
                    text("""
                        UPDATE events SET 
                            status = CASE 
                                WHEN attempts >= :max_attempts THEN 'dlq' 
                                ELSE 'pending' 
                            END,
                            error = :error
                        WHERE id = :id
                    """),
                    {"id": token, "error": error, "max_attempts": self.max_attempts},
                )
                await session.commit()
            
            logfire.warning("Event nacked", event_id=token, error=error)
    
    async def replay(
        self,
        start: datetime,
        end: datetime | None = None,
        event_types: list[str] | None = None,
    ) -> AsyncIterator["Event"]:
        """Replay historical events for debugging.
        
        Events are yielded in timestamp order. Does not affect event status.
        """
        from reflex.core.events import Event
        adapter = TypeAdapter(Event)
        
        with logfire.span("store.replay", start=start.isoformat(), end=end.isoformat() if end else None):
            async with self.session_factory() as session:
                conditions = ["timestamp >= :start"]
                params: dict = {"start": start}
                
                if end:
                    conditions.append("timestamp <= :end")
                    params["end"] = end
                
                if event_types:
                    conditions.append("type = ANY(:types)")
                    params["types"] = event_types
                
                where_clause = " AND ".join(conditions)
                query = text(f"""
                    SELECT payload FROM events 
                    WHERE {where_clause}
                    ORDER BY timestamp
                """)
                
                result = await session.execute(query, params)
                count = 0
                for row in result:
                    yield adapter.validate_json(row.payload)
                    count += 1
                
                logfire.info("Replay completed", event_count=count)
    
    async def dlq_list(self, limit: int = 100) -> list["Event"]:
        """List events in dead-letter queue for inspection."""
        from reflex.core.events import Event
        adapter = TypeAdapter(Event)
        
        async with self.session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT payload, error, attempts, created_at 
                    FROM events 
                    WHERE status = 'dlq'
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            )
            return [adapter.validate_json(row.payload) for row in result]
    
    async def dlq_retry(self, event_id: str) -> bool:
        """Move event from DLQ back to pending for retry."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("""
                    UPDATE events 
                    SET status = 'pending', attempts = 0, error = NULL
                    WHERE id = :id AND status = 'dlq'
                """),
                {"id": event_id},
            )
            await session.commit()
            return result.rowcount > 0
```

-----

### Decision Context

Working memory that accumulates events between actions. Just a Pydantic model with helper methods.

```python
# src/reflex/core/context.py
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Any

from reflex.core.events import Event

class DecisionContext(BaseModel):
    """Working memory during decision-making.
    
    Accumulates events and derived state between actions. When a trigger
    fires and action is taken, the context should be cleared for the next
    decision cycle.
    
    The 'scratch' dict is for your intermediate computations—counts,
    aggregations, flags, etc. Use it however you need.
    """
    
    scope: str = Field(description="Scope identifier, e.g., 'user:123' or 'workflow:abc'")
    events: list[Event] = Field(default_factory=list)
    scratch: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_action_at: datetime | None = Field(default=None)
    
    model_config = {"arbitrary_types_allowed": True}
    
    def add(self, event: Event) -> None:
        """Add event to context."""
        self.events.append(event)
    
    def window(self, seconds: float) -> list[Event]:
        """Get events within time window from now.
        
        Useful for rate limiting, burst detection, etc.
        """
        cutoff = datetime.utcnow() - timedelta(seconds=seconds)
        return [e for e in self.events if e.timestamp >= cutoff]
    
    def of_type(self, *types: str) -> list[Event]:
        """Filter events by type."""
        return [e for e in self.events if e.type in types]
    
    def since_last_action(self) -> list[Event]:
        """Get events since last action was taken."""
        if self.last_action_at is None:
            return self.events
        return [e for e in self.events if e.timestamp > self.last_action_at]
    
    def count_by_type(self) -> dict[str, int]:
        """Count events grouped by type."""
        counts: dict[str, int] = {}
        for e in self.events:
            counts[e.type] = counts.get(e.type, 0) + 1
        return counts
    
    def summarize(self, max_events: int = 10) -> str:
        """Generate human-readable summary for LLM context injection."""
        lines = [
            f"Context scope: {self.scope}",
            f"Total events: {len(self.events)}",
            f"Event types: {self.count_by_type()}",
        ]
        
        recent = self.events[-max_events:]
        if recent:
            lines.append(f"Recent {len(recent)} events:")
            for e in recent:
                lines.append(f"  [{e.type}] {e.timestamp.isoformat()}: {e.source}")
        
        if self.scratch:
            lines.append(f"Scratch state: {self.scratch}")
        
        return "\n".join(lines)
    
    def clear(self) -> None:
        """Reset context after action is taken."""
        self.events.clear()
        self.scratch.clear()
        self.last_action_at = datetime.utcnow()
    
    def mark_action(self) -> None:
        """Mark that action was taken without clearing events."""
        self.last_action_at = datetime.utcnow()
```

-----

### Dependencies

Typed container for injection into PydanticAI agents via `RunContext`.

Following PydanticAI’s pattern: use a dataclass for deps, access via `ctx.deps` in tools.

```python
# src/reflex/core/deps.py
from dataclasses import dataclass
import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from reflex.infra.store import EventStore

@dataclass
class ReflexDeps:
    """Dependencies injected into PydanticAI agents.
    
    Access in tools via RunContext:
    
        @my_agent.tool
        async def my_tool(ctx: RunContext[ReflexDeps], query: str) -> str:
            # Access deps
            result = await ctx.deps.http.get(url)
            await ctx.deps.store.publish(event)
            ...
    
    Add your own dependencies here as needed (Redis client, external APIs, etc.)
    """
    store: EventStore
    http: httpx.AsyncClient
    db: AsyncSession
    scope: str
    
    # Add your dependencies:
    # redis: Redis | None = None
    # stripe: StripeClient | None = None
```

-----

### Filters and Triggers

No protocols or base classes. Just type aliases for functions. This is intentional—functions are simpler, more composable, and easier to test.

```python
# Type definitions (in core/types.py or wherever convenient)
from typing import Callable, Awaitable, Any

# A filter is a sync function: fast, no I/O
Filter = Callable[[Event, DecisionContext], bool]

# A trigger is an async function: may involve LLM calls
Trigger = Callable[[DecisionContext, ReflexDeps], Awaitable[Any]]
```

**Example filters:**

```python
# src/reflex/agent/filters.py
from reflex.core.events import Event
from reflex.core.context import DecisionContext

def keyword_filter(keywords: list[str]) -> Filter:
    """Create a filter that matches events containing any keyword.
    
    Usage:
        error_filter = keyword_filter(["error", "exception", "failed"])
    """
    kw_lower = [k.lower() for k in keywords]
    
    def check(event: Event, ctx: DecisionContext) -> bool:
        payload = event.model_dump_json().lower()
        return any(k in payload for k in kw_lower)
    
    return check

def event_type_filter(*types: str) -> Filter:
    """Filter by event type."""
    def check(event: Event, ctx: DecisionContext) -> bool:
        return event.type in types
    
    return check

def rate_limit_filter(max_per_window: int, window_seconds: float = 60) -> Filter:
    """Reject events if we've accumulated too many in the window.
    
    Useful for preventing runaway processing.
    """
    def check(event: Event, ctx: DecisionContext) -> bool:
        recent = ctx.window(window_seconds)
        return len(recent) < max_per_window
    
    return check

def dedupe_filter(key_fn: Callable[[Event], str], window_seconds: float = 60) -> Filter:
    """Deduplicate events by a key within a time window."""
    def check(event: Event, ctx: DecisionContext) -> bool:
        key = key_fn(event)
        recent = ctx.window(window_seconds)
        seen_keys = {key_fn(e) for e in recent}
        return key not in seen_keys
    
    return check

# Compose filters with standard Python
def all_filters(*filters: Filter) -> Filter:
    """Combine filters with AND logic."""
    def check(event: Event, ctx: DecisionContext) -> bool:
        return all(f(event, ctx) for f in filters)
    return check

def any_filter(*filters: Filter) -> Filter:
    """Combine filters with OR logic."""
    def check(event: Event, ctx: DecisionContext) -> bool:
        return any(f(event, ctx) for f in filters)
    return check
```

**Example triggers:**

```python
# src/reflex/agent/triggers.py
import logfire
from reflex.core.context import DecisionContext
from reflex.core.deps import ReflexDeps
from reflex.agent.agents import alert_agent, summary_agent

async def error_threshold_trigger(
    ctx: DecisionContext,
    deps: ReflexDeps,
    threshold: int = 5,
    window_seconds: float = 60,
) -> str | None:
    """Trigger alert if errors exceed threshold in time window.
    
    Returns alert message if triggered, None otherwise.
    """
    with logfire.span("trigger.error_threshold", threshold=threshold, window=window_seconds):
        errors = [e for e in ctx.window(window_seconds) if "error" in e.type.lower()]
        
        logfire.info("Checking error threshold", error_count=len(errors), threshold=threshold)
        
        if len(errors) >= threshold:
            # Use PydanticAI agent to generate alert
            result = await alert_agent.run(
                f"Generate alert for {len(errors)} errors in {window_seconds}s. "
                f"Events: {[e.model_dump() for e in errors[:10]]}",
                deps=deps,
            )
            return result.data
        
        return None

async def periodic_summary_trigger(
    ctx: DecisionContext,
    deps: ReflexDeps,
    min_events: int = 10,
) -> str | None:
    """Trigger summary generation after accumulating enough events."""
    if len(ctx.events) < min_events:
        return None
    
    result = await summary_agent.run(
        f"Summarize these {len(ctx.events)} events:\n{ctx.summarize()}",
        deps=deps,
    )
    return result.data

async def immediate_trigger(
    ctx: DecisionContext,
    deps: ReflexDeps,
) -> str | None:
    """Trigger on every event (for real-time response patterns)."""
    if not ctx.events:
        return None
    
    latest = ctx.events[-1]
    result = await some_agent.run(
        f"Respond to: {latest.model_dump_json()}",
        deps=deps,
    )
    return result.data
```

-----

### PydanticAI Agents

Agents use PydanticAI’s typed dependency injection and tool system.

```python
# src/reflex/agent/agents.py
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
from datetime import datetime, timedelta

from reflex.core.deps import ReflexDeps
from reflex.config import settings

# --- Alert Agent ---

class AlertResponse(BaseModel):
    """Structured alert response."""
    severity: str  # "low", "medium", "high", "critical"
    summary: str
    recommended_actions: list[str]

alert_agent = Agent(
    settings.default_model,
    deps_type=ReflexDeps,
    result_type=AlertResponse,
    system_prompt="""You are an alert analysis agent. When given error information:
1. Assess severity based on error frequency and type
2. Provide a clear, actionable summary
3. Recommend specific actions to resolve

Keep responses concise and actionable.""",
)

@alert_agent.tool
async def get_recent_events(
    ctx: RunContext[ReflexDeps],
    event_type: str | None = None,
    hours: int = 1,
    limit: int = 20,
) -> str:
    """Fetch recent events for additional context."""
    events = []
    async for event in ctx.deps.store.replay(
        start=datetime.utcnow() - timedelta(hours=hours),
        event_types=[event_type] if event_type else None,
    ):
        events.append(event.model_dump_json())
        if len(events) >= limit:
            break
    
    return f"Found {len(events)} events:\n" + "\n".join(events)

@alert_agent.tool
async def send_slack_notification(
    ctx: RunContext[ReflexDeps],
    channel: str,
    message: str,
) -> str:
    """Send a notification to Slack."""
    # Replace with your actual Slack webhook
    webhook_url = f"https://hooks.slack.com/services/YOUR/WEBHOOK/{channel}"
    
    response = await ctx.deps.http.post(
        webhook_url,
        json={"text": message},
    )
    
    if response.status_code == 200:
        return f"Notification sent to #{channel}"
    else:
        return f"Failed to send: {response.status_code}"

@alert_agent.tool
async def create_incident_ticket(
    ctx: RunContext[ReflexDeps],
    title: str,
    description: str,
    priority: str,
) -> str:
    """Create an incident ticket in your ticketing system."""
    # Replace with your actual ticketing API
    response = await ctx.deps.http.post(
        "https://api.your-ticketing-system.com/incidents",
        json={
            "title": title,
            "description": description,
            "priority": priority,
        },
    )
    
    if response.status_code == 201:
        data = response.json()
        return f"Created incident: {data['id']}"
    else:
        return f"Failed to create incident: {response.status_code}"

# --- Summary Agent ---

class SummaryResponse(BaseModel):
    """Structured summary response."""
    period: str
    event_count: int
    highlights: list[str]
    concerns: list[str]

summary_agent = Agent(
    settings.default_model,
    deps_type=ReflexDeps,
    result_type=SummaryResponse,
    system_prompt="""You are an event summarization agent. Given a set of events:
1. Identify the time period covered
2. Count total events by type
3. Highlight notable patterns or anomalies
4. Flag any concerns that need attention

Be concise and focus on actionable insights.""",
)

# --- Streaming Example ---

async def stream_response(prompt: str, deps: ReflexDeps):
    """Example of streaming agent response."""
    async with alert_agent.run_stream(prompt, deps=deps) as response:
        async for chunk in response.stream_text():
            yield chunk
```

-----

### Agent Loop

You write this. Here’s a reference implementation:

```python
# src/reflex/agent/loop.py
import asyncio
import logfire
from typing import Callable, Awaitable, Any

from reflex.core.events import Event
from reflex.core.context import DecisionContext
from reflex.core.deps import ReflexDeps
from reflex.infra.store import EventStore
from reflex.infra.locks import ScopedLocks

# Type aliases
Filter = Callable[[Event, DecisionContext], bool]
Trigger = Callable[[DecisionContext, ReflexDeps], Awaitable[Any]]

async def run_agent_loop(
    store: EventStore,
    deps: ReflexDeps,
    filters: list[Filter],
    trigger: Trigger,
    scope: str = "default",
    locks: ScopedLocks | None = None,
) -> None:
    """Reference agent loop implementation.
    
    This is meant to be customized or replaced entirely. The pattern is:
    
    1. Subscribe to events from the store
    2. Apply filters (fast, sync) to determine relevance
    3. Accumulate relevant events in context
    4. Check trigger (potentially slow, may involve LLM)
    5. If trigger fires, take action and clear context
    6. Ack/nack the event
    
    Args:
        store: EventStore to subscribe to
        deps: Dependencies for agents
        filters: List of filter functions (event passes if ANY filter returns True)
        trigger: Trigger function to evaluate
        scope: Scope identifier for this loop (for locking and context)
        locks: Optional scoped locks for concurrency control
    """
    ctx = DecisionContext(scope=scope)
    
    logfire.info("Agent loop starting", scope=scope, filter_count=len(filters))
    
    async for event, token in store.subscribe():
        with logfire.span(
            "agent.process_event",
            event_id=event.id,
            event_type=event.type,
            scope=scope,
        ):
            try:
                # Apply filters
                relevant = any(f(event, ctx) for f in filters)
                logfire.debug("Filter result", relevant=relevant)
                
                if not relevant:
                    await store.ack(token)
                    continue
                
                # Accumulate in context
                ctx.add(event)
                logfire.info(
                    "Event added to context",
                    context_size=len(ctx.events),
                    event_types=ctx.count_by_type(),
                )
                
                # Acquire lock if using scoped locking
                if locks:
                    async with locks.acquire(scope):
                        result = await trigger(ctx, deps)
                else:
                    result = await trigger(ctx, deps)
                
                # Handle trigger result
                if result is not None:
                    logfire.info(
                        "Trigger fired",
                        result_type=type(result).__name__,
                        context_size=len(ctx.events),
                    )
                    ctx.clear()
                
                await store.ack(token)
                
            except asyncio.CancelledError:
                # Graceful shutdown
                logfire.info("Agent loop cancelled", scope=scope)
                raise
                
            except Exception as e:
                logfire.error(
                    "Event processing failed",
                    event_id=event.id,
                    error=str(e),
                    exc_info=True,
                )
                await store.nack(token, str(e))
```

**Alternative patterns you might use:**

```python
# Real-time response (trigger on every event)
async def realtime_loop(store, deps, handler):
    async for event, token in store.subscribe():
        try:
            await handler(event, deps)
            await store.ack(token)
        except Exception as e:
            await store.nack(token, str(e))

# Batch processing (accumulate then process)
async def batch_loop(store, deps, processor, batch_size=100, timeout=60):
    batch = []
    last_process = datetime.utcnow()
    
    async for event, token in store.subscribe():
        batch.append((event, token))
        
        should_process = (
            len(batch) >= batch_size or
            (datetime.utcnow() - last_process).seconds >= timeout
        )
        
        if should_process:
            try:
                await processor([e for e, _ in batch], deps)
                for _, token in batch:
                    await store.ack(token)
            except Exception as e:
                for _, token in batch:
                    await store.nack(token, str(e))
            
            batch.clear()
            last_process = datetime.utcnow()

# Multiple concurrent consumers
async def parallel_loop(store, deps, trigger, num_workers=4):
    async def worker(worker_id):
        ctx = DecisionContext(scope=f"worker:{worker_id}")
        async for event, token in store.subscribe():
            # Each worker processes independently
            ...
    
    await asyncio.gather(*[worker(i) for i in range(num_workers)])
```

-----

### Scoped Locking

Simple in-memory scoped locking for single-process deployments. For multi-process, use Postgres advisory locks or Redis.

```python
# src/reflex/infra/locks.py
from collections import defaultdict
from contextlib import asynccontextmanager
import asyncio

class ScopedLocks:
    """In-memory scoped locking.
    
    Prevents concurrent trigger execution for the same scope.
    
    Usage:
        locks = ScopedLocks()
        
        async with locks.acquire("user:123"):
            # Only one coroutine can be here for "user:123"
            await do_work()
    
    For multi-process deployments, use Postgres advisory locks:
    
        SELECT pg_advisory_lock(hashtext('user:123'));
        -- do work --
        SELECT pg_advisory_unlock(hashtext('user:123'));
    
    Or Redis:
    
        async with redis.lock(f"reflex:lock:{scope}"):
            await do_work()
    """
    
    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
    
    @asynccontextmanager
    async def acquire(self, scope: str):
        """Acquire lock for scope."""
        async with self._locks[scope]:
            yield
    
    def is_locked(self, scope: str) -> bool:
        """Check if scope is currently locked."""
        return scope in self._locks and self._locks[scope].locked()
```

-----

### Database Setup

Async Postgres with connection pooling configured for production.

```python
# src/reflex/infra/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import SQLModel
import asyncpg

from reflex.config import settings

# SQLAlchemy async engine
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,  # Validate connections before use
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_pool_max_overflow,
    echo=settings.environment == "development",
)

# Session factory
SessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Critical for async - prevents implicit I/O
)

async def get_session() -> AsyncSession:
    """Dependency for FastAPI routes."""
    async with SessionFactory() as session:
        yield session

async def create_raw_pool() -> asyncpg.Pool:
    """Create raw asyncpg pool for LISTEN/NOTIFY.
    
    SQLAlchemy doesn't expose LISTEN/NOTIFY, so we need a raw pool.
    """
    # Convert SQLAlchemy URL to asyncpg format
    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.create_pool(url)

async def init_database() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
```

-----

### Observability

Pre-configured Logfire with all integrations enabled.

```python
# src/reflex/infra/observability.py
import logfire
from fastapi import FastAPI

from reflex.config import settings

def configure_observability() -> None:
    """Configure Logfire. Call once at startup."""
    logfire.configure(
        token=settings.logfire_token,
        service_name="reflex",
        service_version=settings.version,
        environment=settings.environment,
        console=settings.environment == "development",
    )

def instrument_app(app: FastAPI) -> None:
    """Instrument FastAPI and all integrations.
    
    This gives you:
    - HTTP request/response tracing
    - PydanticAI agent calls with token usage
    - Database queries
    - Outgoing HTTP requests
    - Full distributed tracing across all layers
    """
    logfire.instrument_fastapi(app)
    logfire.instrument_pydantic_ai()
    logfire.instrument_asyncpg()
    logfire.instrument_httpx()
```

-----

### FastAPI Application

Proper lifecycle management with graceful shutdown.

```python
# src/reflex/api/app.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
import httpx
import asyncio

from reflex.config import settings
from reflex.infra.database import engine, SessionFactory, create_raw_pool, init_database
from reflex.infra.store import EventStore
from reflex.infra.locks import ScopedLocks
from reflex.infra.observability import configure_observability, instrument_app
from reflex.core.deps import ReflexDeps
from reflex.agent.loop import run_agent_loop
from reflex.agent.filters import keyword_filter, rate_limit_filter
from reflex.agent.triggers import error_threshold_trigger
from reflex.api.routes import events, health, ws

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management.
    
    Startup:
    1. Configure observability
    2. Initialize database
    3. Create connection pools
    4. Start background agent loop
    
    Shutdown:
    1. Cancel agent loop gracefully
    2. Close connection pools
    3. Dispose of engine
    """
    # --- Startup ---
    configure_observability()
    
    # Initialize database
    await init_database()
    
    # Create connection pools
    raw_pool = await create_raw_pool()
    http_client = httpx.AsyncClient(timeout=30.0)
    
    # Create stores
    store = EventStore(SessionFactory, raw_pool)
    locks = ScopedLocks()
    
    # Store in app state for access in routes
    app.state.store = store
    app.state.http = http_client
    app.state.pool = raw_pool
    app.state.locks = locks
    
    # Create deps for agent loop
    async with SessionFactory() as db:
        deps = ReflexDeps(
            store=store,
            http=http_client,
            db=db,
            scope="main",
        )
        
        # Start agent loop as background task
        app.state.agent_task = asyncio.create_task(
            run_agent_loop(
                store=store,
                deps=deps,
                filters=[
                    keyword_filter(["error", "exception", "failed"]),
                    rate_limit_filter(1000, 60),
                ],
                trigger=error_threshold_trigger,
                scope="main",
                locks=locks,
            )
        )
    
    yield
    
    # --- Shutdown ---
    
    # Cancel agent loop gracefully
    app.state.agent_task.cancel()
    try:
        await app.state.agent_task
    except asyncio.CancelledError:
        pass
    
    # Close connections
    await http_client.aclose()
    await raw_pool.close()
    await engine.dispose()

# Create application
app = FastAPI(
    title="Reflex",
    description="Real-time AI agent",
    version=settings.version,
    lifespan=lifespan,
)

# Instrument for observability
instrument_app(app)

# Include routes
app.include_router(health.router, tags=["health"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(ws.router, prefix="/ws", tags=["websocket"])
```

-----

### API Routes

```python
# src/reflex/api/routes/health.py
from fastapi import APIRouter, Request
from datetime import datetime

router = APIRouter()

@router.get("/health")
async def health():
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }

@router.get("/ready")
async def ready(request: Request):
    """Readiness check - verifies database connectivity."""
    try:
        # Try to query the database
        async for _ in request.app.state.store.replay(
            start=datetime.utcnow(),
            end=datetime.utcnow(),
        ):
            break
        return {"status": "ready"}
    except Exception as e:
        return {"status": "not ready", "error": str(e)}, 503
```

```python
# src/reflex/api/routes/events.py
from fastapi import APIRouter, Request, HTTPException
from datetime import datetime

from reflex.core.events import Event

router = APIRouter()

@router.post("/")
async def publish_event(event: Event, request: Request):
    """Publish an event to the store."""
    await request.app.state.store.publish(event)
    return {"id": event.id, "status": "published"}

@router.get("/dlq")
async def list_dlq(request: Request, limit: int = 100):
    """List events in dead-letter queue."""
    events = await request.app.state.store.dlq_list(limit)
    return {
        "count": len(events),
        "events": [e.model_dump() for e in events],
    }

@router.post("/dlq/{event_id}/retry")
async def retry_dlq_event(event_id: str, request: Request):
    """Move event from DLQ back to pending."""
    success = await request.app.state.store.dlq_retry(event_id)
    if not success:
        raise HTTPException(404, "Event not found in DLQ")
    return {"status": "retrying", "event_id": event_id}
```

```python
# src/reflex/api/routes/ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
import logfire

from reflex.core.events import WebSocketEvent

router = APIRouter()

@router.websocket("/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    request: Request,
):
    """WebSocket endpoint for real-time event ingestion."""
    await websocket.accept()
    store = request.app.state.store
    
    logfire.info("WebSocket connected", client_id=client_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            event = WebSocketEvent(
                source=f"ws:{client_id}",
                connection_id=client_id,
                content=data.get("content", ""),
            )
            
            await store.publish(event)
            await websocket.send_json({"ack": event.id})
            
    except WebSocketDisconnect:
        logfire.info("WebSocket disconnected", client_id=client_id)
```

-----

### API Dependencies

```python
# src/reflex/api/deps.py
from fastapi import Request, Depends

from reflex.infra.store import EventStore
from reflex.infra.database import get_session
from reflex.core.deps import ReflexDeps

def get_store(request: Request) -> EventStore:
    return request.app.state.store

def get_http(request: Request):
    return request.app.state.http

async def get_deps(
    request: Request,
    db=Depends(get_session),
) -> ReflexDeps:
    """Get ReflexDeps for use in route handlers."""
    return ReflexDeps(
        store=get_store(request),
        http=get_http(request),
        db=db,
        scope="api",
    )
```

-----

## Async Patterns Reference

Standard Python patterns—no framework abstractions.

### Sequential Actions

```python
async def my_trigger(ctx: DecisionContext, deps: ReflexDeps):
    # Just call agents in sequence
    analysis = await analyst_agent.run(ctx.summarize(), deps=deps)
    response = await responder_agent.run(analysis.data, deps=deps)
    return response.data
```

### Parallel Actions

```python
async def my_trigger(ctx: DecisionContext, deps: ReflexDeps):
    # Standard asyncio.gather
    results = await asyncio.gather(
        agent_a.run(ctx.summarize(), deps=deps),
        agent_b.run(ctx.summarize(), deps=deps),
    )
    return {"a": results[0].data, "b": results[1].data}
```

### First to Complete

```python
async def my_trigger(ctx: DecisionContext, deps: ReflexDeps):
    tasks = [
        asyncio.create_task(fast_agent.run(ctx.summarize(), deps=deps)),
        asyncio.create_task(thorough_agent.run(ctx.summarize(), deps=deps)),
    ]
    
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    
    for task in pending:
        task.cancel()
    
    return done.pop().result().data
```

### Retry with Backoff

Use `tenacity`:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
async def reliable_trigger(ctx: DecisionContext, deps: ReflexDeps):
    return await flaky_agent.run(ctx.summarize(), deps=deps)
```

### Timeout

```python
async def my_trigger(ctx: DecisionContext, deps: ReflexDeps):
    try:
        async with asyncio.timeout(10):
            return await slow_agent.run(ctx.summarize(), deps=deps)
    except asyncio.TimeoutError:
        return await fallback_agent.run("Quick response needed", deps=deps)
```

### Conditional Routing

```python
async def my_trigger(ctx: DecisionContext, deps: ReflexDeps):
    errors = ctx.of_type("error")
    
    if len(errors) > 10:
        return await escalation_agent.run(ctx.summarize(), deps=deps)
    elif len(errors) > 0:
        return await alert_agent.run(ctx.summarize(), deps=deps)
    else:
        return None
```

### Pipeline

```python
async def pipeline_trigger(ctx: DecisionContext, deps: ReflexDeps):
    classified = await classifier_agent.run(ctx.summarize(), deps=deps)
    enriched = await enricher_agent.run(classified.data, deps=deps)
    response = await responder_agent.run(enriched.data, deps=deps)
    return response.data
```

### Supervisor/Worker

```python
async def supervisor_trigger(ctx: DecisionContext, deps: ReflexDeps):
    plan = await planner_agent.run(ctx.summarize(), deps=deps)
    
    results = []
    for task in plan.data["tasks"]:
        if task["type"] == "research":
            r = await research_agent.run(task["query"], deps=deps)
        elif task["type"] == "analyze":
            r = await analysis_agent.run(task["data"], deps=deps)
        results.append(r.data)
    
    return await synthesis_agent.run(str(results), deps=deps)
```

-----

## Docker Setup

### docker-compose.yml

```yaml
services:
  app:
    build:
      context: .
      dockerfile: docker/Dockerfile.dev
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://reflex:reflex@db:5432/reflex
      - LOGFIRE_TOKEN=${LOGFIRE_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ENVIRONMENT=development
    volumes:
      - ./src:/app/src
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: reflex
      POSTGRES_PASSWORD: reflex
      POSTGRES_DB: reflex
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U reflex"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### Dockerfile.dev

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml README.md ./

# Install dependencies
RUN uv pip install --system -e ".[dev]"

# Copy source (mounted as volume in dev, but needed for initial build)
COPY src/ src/

# Run with hot reload
CMD ["uvicorn", "reflex.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "src"]
```

### Dockerfile (Production)

```dockerfile
FROM python:3.12-slim as builder

WORKDIR /app

# Install uv
RUN pip install uv

# Copy and install dependencies
COPY pyproject.toml README.md ./
RUN uv pip install --system .

FROM python:3.12-slim

WORKDIR /app

# Copy installed packages
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source
COPY src/ src/

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "reflex.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

-----

## Makefile

```makefile
.PHONY: dev test lint type-check format clean logs shell

# Development
dev:
	docker compose up

dev-build:
	docker compose up --build

dev-down:
	docker compose down

logs:
	docker compose logs -f app

shell:
	docker compose exec app bash

db-shell:
	docker compose exec db psql -U reflex

# Testing
test:
	docker compose run --rm app pytest -v

test-cov:
	docker compose run --rm app pytest --cov=reflex --cov-report=html

# Code quality
lint:
	ruff check src tests

lint-fix:
	ruff check --fix src tests

format:
	ruff format src tests

type-check:
	pyright src

check: lint type-check test

# Database
migrate:
	docker compose run --rm app python scripts/migrate.py

# Utilities
replay:
	docker compose run --rm app python scripts/replay.py $(ARGS)

dlq:
	docker compose run --rm app python scripts/dlq.py

# Cleanup
clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
```

-----

## Scripts

### Replay Utility

```python
#!/usr/bin/env python
# scripts/replay.py
"""
Replay events for debugging.

Usage:
    python scripts/replay.py --start 2024-01-01T00:00:00
    python scripts/replay.py --last 1h
    python scripts/replay.py --last 30m --types error,alert
    python scripts/replay.py --last 1h --output events.jsonl
"""
import asyncio
import argparse
import sys
from datetime import datetime, timedelta
import re

from reflex.infra.database import SessionFactory, create_raw_pool
from reflex.infra.store import EventStore

def parse_duration(s: str) -> timedelta:
    """Parse duration string like '1h', '30m', '2d'."""
    match = re.match(r'^(\d+)([smhd])$', s)
    if not match:
        raise ValueError(f"Invalid duration: {s}")
    
    value, unit = int(match.group(1)), match.group(2)
    
    if unit == 's':
        return timedelta(seconds=value)
    elif unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)

async def main(args):
    pool = await create_raw_pool()
    store = EventStore(SessionFactory, pool)
    
    # Determine time range
    if args.last:
        duration = parse_duration(args.last)
        start = datetime.utcnow() - duration
        end = None
    else:
        start = datetime.fromisoformat(args.start)
        end = datetime.fromisoformat(args.end) if args.end else None
    
    types = args.types.split(",") if args.types else None
    
    # Output
    output = open(args.output, 'w') if args.output else sys.stdout
    
    count = 0
    async for event in store.replay(start, end, types):
        output.write(event.model_dump_json() + "\n")
        count += 1
    
    if args.output:
        output.close()
    
    print(f"\nReplayed {count} events", file=sys.stderr)
    
    await pool.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay events for debugging")
    parser.add_argument("--start", help="Start time (ISO format)")
    parser.add_argument("--end", help="End time (ISO format)")
    parser.add_argument("--last", help="Duration like 1h, 30m, 2d")
    parser.add_argument("--types", help="Comma-separated event types")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    
    args = parser.parse_args()
    
    if not args.start and not args.last:
        parser.error("Either --start or --last is required")
    
    asyncio.run(main(args))
```

### DLQ Management

```python
#!/usr/bin/env python
# scripts/dlq.py
"""
Manage dead-letter queue.

Usage:
    python scripts/dlq.py list
    python scripts/dlq.py retry <event_id>
    python scripts/dlq.py retry-all
    python scripts/dlq.py purge
"""
import asyncio
import argparse

from reflex.infra.database import SessionFactory, create_raw_pool
from reflex.infra.store import EventStore

async def list_dlq(store: EventStore, limit: int):
    events = await store.dlq_list(limit)
    
    if not events:
        print("DLQ is empty")
        return
    
    print(f"Found {len(events)} events in DLQ:\n")
    for event in events:
        print(f"  ID: {event.id}")
        print(f"  Type: {event.type}")
        print(f"  Source: {event.source}")
        print(f"  Timestamp: {event.timestamp}")
        print()

async def retry_event(store: EventStore, event_id: str):
    success = await store.dlq_retry(event_id)
    if success:
        print(f"Event {event_id} moved back to pending")
    else:
        print(f"Event {event_id} not found in DLQ")

async def main(args):
    pool = await create_raw_pool()
    store = EventStore(SessionFactory, pool)
    
    if args.command == "list":
        await list_dlq(store, args.limit)
    elif args.command == "retry":
        await retry_event(store, args.event_id)
    
    await pool.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage dead-letter queue")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # list
    list_parser = subparsers.add_parser("list", help="List DLQ events")
    list_parser.add_argument("--limit", type=int, default=100)
    
    # retry
    retry_parser = subparsers.add_parser("retry", help="Retry a DLQ event")
    retry_parser.add_argument("event_id")
    
    args = parser.parse_args()
    asyncio.run(main(args))
```

-----

## CI/CD

### GitHub Actions CI

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: reflex
          POSTGRES_PASSWORD: reflex
          POSTGRES_DB: reflex_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      
      - name: Install uv
        run: pip install uv
      
      - name: Install dependencies
        run: uv pip install --system -e ".[dev]"
      
      - name: Lint
        run: ruff check src tests
      
      - name: Type check
        run: pyright src
      
      - name: Test
        run: pytest --cov=reflex --cov-report=xml
        env:
          DATABASE_URL: postgresql+asyncpg://reflex:reflex@localhost:5432/reflex_test
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: coverage.xml

  build:
    runs-on: ubuntu-latest
    needs: check
    if: github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Build image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/Dockerfile
          push: false
          tags: reflex:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

-----

## Configuration Files

### pyproject.toml

```toml
[project]
name = "reflex"
version = "0.5.0"
description = "Real-time AI agent template project"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.10",
    "pydantic-ai>=1.0",
    "pydantic-settings>=2.0",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlmodel>=0.0.22",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "httpx>=0.28",
    "logfire>=2.0",
    "tenacity>=9.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "ruff>=0.8",
    "pyright>=1.1.390",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/reflex"]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E", "W",     # pycodestyle
    "F",          # pyflakes
    "I",          # isort
    "B",          # flake8-bugbear
    "C4",         # flake8-comprehensions
    "UP",         # pyupgrade
    "ASYNC",      # flake8-async (critical for this project)
    "TCH",        # TYPE_CHECKING imports
    "S",          # flake8-bandit (security)
    "RUF",        # Ruff-specific rules
]
ignore = [
    "S101",       # assert is fine in tests
]

[tool.ruff.lint.isort]
known-first-party = ["reflex"]

[tool.pyright]
pythonVersion = "3.12"
pythonPlatform = "Linux"
typeCheckingMode = "strict"
reportMissingTypeStubs = false
reportUnknownMemberType = false
venvPath = "."
venv = ".venv"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
filterwarnings = [
    "ignore::DeprecationWarning",
]
```

### .env.example

```bash
# Database
DATABASE_URL=postgresql+asyncpg://reflex:reflex@localhost:5432/reflex
DATABASE_POOL_SIZE=5
DATABASE_POOL_MAX_OVERFLOW=10

# API
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true

# Observability
LOGFIRE_TOKEN=
LOG_LEVEL=INFO

# AI
OPENAI_API_KEY=
DEFAULT_MODEL=openai:gpt-4o-mini

# Event Processing
EVENT_MAX_ATTEMPTS=3
EVENT_RETRY_BASE_DELAY=1.0
EVENT_RETRY_MAX_DELAY=60.0

# App
ENVIRONMENT=development
VERSION=0.1.0
```

-----

## Anti-Patterns to Avoid

1. **Blocking calls in async context.** Never use `time.sleep()`, `requests`, or sync database calls. The `ASYNC` ruff rule catches many of these.
1. **Global mutable state.** Use `app.state` for shared resources, pass dependencies explicitly via `ReflexDeps`.
1. **Lazy-loaded relationships.** SQLModel/SQLAlchemy lazy loading triggers implicit I/O. Use `selectin` or `joined` loading, or just avoid relationships in this architecture.
1. **Polling when LISTEN/NOTIFY exists.** The EventStore uses Postgres NOTIFY—don’t add polling loops.
1. **Swallowing exceptions.** Always log exceptions with `exc_info=True` before nacking events.
1. **Unbounded retries.** Use the `max_attempts` configuration. Events that keep failing go to DLQ.
1. **Missing graceful shutdown.** The lifespan handler cancels background tasks properly—don’t circumvent this.
1. **Over-abstraction.** If you’re writing wrappers around `asyncio.gather` or building a “pipeline framework,” stop. Just write the async code directly.

-----

## What to Keep vs Replace

|Directory        |Action     |Notes                                             |
|-----------------|-----------|--------------------------------------------------|
|`infra/`         |**Keep**   |Database, store, observability, locks             |
|`core/events.py` |**Modify** |Add your event types to the union                 |
|`core/context.py`|**Keep**   |Unless you need different context behavior        |
|`core/deps.py`   |**Modify** |Add your dependencies (Redis, external APIs, etc.)|
|`agent/`         |**Replace**|This is your domain logic                         |
|`api/app.py`     |**Keep**   |Lifespan management and setup                     |
|`api/routes/`    |**Modify** |Add your endpoints                                |
|`docker/`        |**Keep**   |Unless changing infrastructure                    |
|`scripts/`       |**Keep**   |Useful utilities                                  |
|`.github/`       |**Keep**   |CI/CD templates                                   |

-----

## Getting Started

### 1. Clone and Configure

```bash
git clone https://github.com/yourorg/reflex my-agent
cd my-agent
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start Development

```bash
make dev
# Or: docker compose up
```

### 3. Verify It’s Running

```bash
# Health check
curl http://localhost:8000/health

# Publish a test event
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"type": "http.request", "source": "test", "method": "GET", "path": "/test"}'

# Connect via WebSocket
websocat ws://localhost:8000/ws/test-client
```

### 4. Build Your Agent

1. Define your event types in `src/reflex/core/events.py`
1. Add your dependencies to `src/reflex/core/deps.py`
1. Write your filters in `src/reflex/agent/filters.py`
1. Write your triggers in `src/reflex/agent/triggers.py`
1. Create your PydanticAI agents in `src/reflex/agent/agents.py`
1. Customize (or replace) the loop in `src/reflex/agent/loop.py`

-----

## Success Criteria

1. **Zero to running:** `git clone && docker compose up` works in under 2 minutes.
1. **Clear boundaries:** Obvious what to keep vs replace.
1. **Production-ready:** Health checks, graceful shutdown, connection pooling, DLQ all work.
1. **Full observability:** Logfire traces from HTTP request through agent to database.
1. **Type safety:** Pyright strict mode passes with no errors.
1. **No magic:** A Python developer can read any file and understand it without docs.

-----

## References

- [PydanticAI Documentation](https://ai.pydantic.dev/)
- [Pydantic v2 Documentation](https://docs.pydantic.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [Logfire Documentation](https://logfire.pydantic.dev/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)