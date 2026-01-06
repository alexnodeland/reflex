# Reflex

## Product Requirements Document

**Version:** 0.3.0  
**Status:** Draft  
**Author:** Alex Nodeland  
**Date:** January 2026

-----

## Executive Summary

Reflex is a Python library for building real-time AI agents as continuous control systems. It provides minimal primitives—event storage, context accumulation, and PydanticAI integration—that users compose with standard Python async patterns.

The core insight: agents should behave like control systems with closed perception-action loops. Reflex provides the building blocks; you write the loops.

-----

## Problem Statement

Current agentic AI architectures suffer from fundamental limitations:

**Polling-based interaction:** Most agent frameworks operate as expensive polling loops—wake up, check for input, process, respond, sleep.

**Blocking reasoning:** Perception stops while the agent thinks. No continuous awareness.

**Ad-hoc state management:** No separation between working memory and durable storage. Context is string concatenation.

**Poor observability:** Debugging means reconstructing what the agent “saw” and “thought.”

**Framework lock-in:** DSLs and custom abstractions that fight Python rather than embrace it.

-----

## Design Philosophy

**It’s just Python.** No DSLs, no special combinators, no magic. If you know async Python, you know Reflex.

**Library, not framework.** You call Reflex; Reflex doesn’t call you. Write your own loops, use the primitives you need.

**Type hints as source of truth.** Following PydanticAI, types drive validation and IDE support.

**Async-first.** Every I/O operation is async. No blocking calls.

**Observability via Logfire.** Instrument once, trace everything.

-----

## Core Primitives

Reflex provides four things:

1. **Event types** — Pydantic models with discriminated unions
1. **EventStore** — Persistence, replay, acknowledgment
1. **DecisionContext** — Working memory that accumulates between actions
1. **ReflexDeps** — Typed dependency container for PydanticAI agents

Everything else is standard Python.

-----

## Event System

Events use Pydantic v2 discriminated unions for efficient validation.

```python
from pydantic import BaseModel, Field
from typing import Literal, Annotated, Union
from datetime import datetime
from uuid import uuid4

class EventMeta(BaseModel):
    """Trace context for observability."""
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None
    causation_id: str | None = None

class BaseEvent(BaseModel):
    """Common fields for all events."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str
    meta: EventMeta = Field(default_factory=EventMeta)

class WebSocketEvent(BaseEvent):
    type: Literal["ws.message"] = "ws.message"
    connection_id: str
    content: str

class HTTPEvent(BaseEvent):
    type: Literal["http.request"] = "http.request"
    method: str
    path: str
    body: dict | None = None

class FileEvent(BaseEvent):
    type: Literal["file.change"] = "file.change"
    path: str
    change_type: Literal["created", "modified", "deleted"]

class TimerEvent(BaseEvent):
    type: Literal["timer.tick"] = "timer.tick"
    timer_name: str

# Discriminated union — validator checks 'type' first
Event = Annotated[
    Union[WebSocketEvent, HTTPEvent, FileEvent, TimerEvent],
    Field(discriminator="type")
]
```

Users extend with their own event types:

```python
class SlackMessageEvent(BaseEvent):
    type: Literal["slack.message"] = "slack.message"
    channel: str
    user: str
    text: str

# Extend the union
MyEvent = Annotated[
    Union[WebSocketEvent, HTTPEvent, SlackMessageEvent],
    Field(discriminator="type")
]
```

-----

## Event Store

SQLite-backed persistence with async sessions. Simple interface:

```python
from typing import AsyncIterator
from datetime import datetime

class EventStore:
    """Persist and retrieve events."""
    
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
```

### SQLite Implementation

```python
from sqlmodel import SQLModel, Field as SQLField
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from pydantic import TypeAdapter
import asyncio

class EventRecord(SQLModel, table=True):
    __tablename__ = "events"
    
    id: str = SQLField(primary_key=True)
    type: str = SQLField(index=True)
    source: str
    timestamp: datetime = SQLField(index=True)
    payload: str  # JSON
    status: str = SQLField(default="pending", index=True)
    attempts: int = SQLField(default=0)
    error: str | None = None

class SQLiteEventStore:
    def __init__(self, db_url: str = "sqlite+aiosqlite:///reflex.db"):
        self.engine = create_async_engine(db_url)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self.max_attempts = 3
        self._event_adapter = TypeAdapter(Event)
        self._notify = asyncio.Event()
    
    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    
    async def publish(self, event: Event) -> None:
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
        from sqlmodel import select
        
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
                records = result.all()
                
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
                except asyncio.TimeoutError:
                    pass
    
    async def ack(self, token: str) -> None:
        async with self.session_factory() as session:
            record = await session.get(EventRecord, token)
            if record:
                record.status = "completed"
                session.add(record)
                await session.commit()
    
    async def nack(self, token: str, error: str | None = None) -> None:
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
```

**Note on polling:** The implementation uses `asyncio.Event` for in-process notification, reducing polling when events are published from the same process. For multi-process deployments, upgrade to Postgres with LISTEN/NOTIFY.

-----

## Decision Context

Working memory that accumulates events between actions. Just a Pydantic model:

```python
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Any

class DecisionContext(BaseModel):
    """Working memory during decision-making."""
    
    scope: str
    events: list[Event] = Field(default_factory=list)
    scratch: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def add(self, event: Event) -> None:
        self.events.append(event)
    
    def window(self, seconds: float) -> list[Event]:
        cutoff = datetime.utcnow() - timedelta(seconds=seconds)
        return [e for e in self.events if e.timestamp >= cutoff]
    
    def of_type(self, *types: str) -> list[Event]:
        return [e for e in self.events if e.type in types]
    
    def clear(self) -> None:
        self.events.clear()
        self.scratch.clear()
```

-----

## Dependencies

Typed container for PydanticAI’s `RunContext` pattern:

```python
from dataclasses import dataclass
import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

@dataclass
class ReflexDeps:
    """Dependencies injected into agents."""
    event_store: EventStore
    http: httpx.AsyncClient
    db: AsyncSession
    scope: str
```

-----

## Filters and Triggers

No protocols. Just functions:

```python
from typing import Callable, Awaitable

# A filter is a function that returns True if the event is relevant
Filter = Callable[[Event, DecisionContext], bool]

# A trigger is an async function that returns a response (or None)
Trigger = Callable[[DecisionContext, ReflexDeps], Awaitable[Any]]
```

Example filter:

```python
def keyword_filter(keywords: list[str]) -> Filter:
    """Create a filter that matches events containing keywords."""
    kw_lower = [k.lower() for k in keywords]
    
    def check(event: Event, ctx: DecisionContext) -> bool:
        payload = event.model_dump_json().lower()
        return any(k in payload for k in kw_lower)
    
    return check
```

Example trigger using PydanticAI directly:

```python
from pydantic_ai import Agent, RunContext

alert_agent = Agent(
    "openai:gpt-4o-mini",
    deps_type=ReflexDeps,
    system_prompt="You are an alert agent. Summarize events and recommend actions.",
)

@alert_agent.tool
async def get_event_count(ctx: RunContext[ReflexDeps]) -> int:
    """Get the number of events in current context."""
    # Access context through deps
    return len(ctx.deps.context.events)

async def alert_trigger(ctx: DecisionContext, deps: ReflexDeps) -> str | None:
    """Trigger alert if more than 5 errors in last minute."""
    errors = [e for e in ctx.window(60) if "error" in e.type]
    
    if len(errors) >= 5:
        result = await alert_agent.run(
            f"Summarize these {len(errors)} errors and recommend action: "
            + "\n".join(e.model_dump_json() for e in errors[:10]),
            deps=deps,
        )
        return result.data
    
    return None
```

-----

## Writing Loops

You write your own loops. Here’s a basic pattern:

```python
async def run_agent(
    store: EventStore,
    deps: ReflexDeps,
    filters: list[Filter],
    trigger: Trigger,
    scope: str = "default",
):
    """Basic agent loop."""
    ctx = DecisionContext(scope=scope)
    
    async for event, token in store.subscribe():
        try:
            # Check filters
            if not any(f(event, ctx) for f in filters):
                await store.ack(token)
                continue
            
            # Accumulate
            ctx.add(event)
            
            # Check trigger
            if result := await trigger(ctx, deps):
                # Action was taken, reset context
                ctx.clear()
            
            await store.ack(token)
            
        except Exception as e:
            await store.nack(token, str(e))
```

**That’s it.** No framework magic. Customize as needed:

```python
async def run_agent_with_timeout(
    store: EventStore,
    deps: ReflexDeps,
    trigger: Trigger,
    scope: str,
    action_timeout: float = 30.0,
):
    """Agent loop with action timeout."""
    ctx = DecisionContext(scope=scope)
    
    async for event, token in store.subscribe():
        ctx.add(event)
        
        try:
            async with asyncio.timeout(action_timeout):
                if result := await trigger(ctx, deps):
                    ctx.clear()
            await store.ack(token)
        except asyncio.TimeoutError:
            await store.nack(token, "action timeout")
        except Exception as e:
            await store.nack(token, str(e))
```

-----

## Patterns

Standard Python patterns, not framework abstractions.

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
    # Just use if/elif
    errors = ctx.of_type("error")
    
    if len(errors) > 10:
        return await escalation_agent.run(ctx.summarize(), deps=deps)
    elif len(errors) > 0:
        return await alert_agent.run(ctx.summarize(), deps=deps)
    else:
        return None  # No action
```

### Pipelines

```python
async def pipeline_trigger(ctx: DecisionContext, deps: ReflexDeps):
    # Chain of agents, each transforming the output
    classified = await classifier_agent.run(ctx.summarize(), deps=deps)
    enriched = await enricher_agent.run(classified.data, deps=deps)
    response = await responder_agent.run(enriched.data, deps=deps)
    return response.data
```

### Supervisor/Worker

```python
async def supervisor_trigger(ctx: DecisionContext, deps: ReflexDeps):
    # Supervisor decides what to delegate
    plan = await planner_agent.run(ctx.summarize(), deps=deps)
    
    # Execute subtasks
    results = []
    for task in plan.data["tasks"]:
        if task["type"] == "research":
            r = await research_agent.run(task["query"], deps=deps)
        elif task["type"] == "analyze":
            r = await analysis_agent.run(task["data"], deps=deps)
        results.append(r.data)
    
    # Synthesize
    return await synthesis_agent.run(str(results), deps=deps)
```

-----

## Scoped Locking

Prevent concurrent actions for the same scope using `asyncio.Lock`:

```python
from collections import defaultdict
import asyncio

class ScopedLocks:
    """Simple in-memory scoped locking."""
    
    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
    
    async def __call__(self, scope: str):
        return self._locks[scope]

locks = ScopedLocks()

async def run_agent_with_lock(store, deps, trigger, scope):
    ctx = DecisionContext(scope=scope)
    
    async for event, token in store.subscribe():
        ctx.add(event)
        
        async with await locks(scope):
            if result := await trigger(ctx, deps):
                ctx.clear()
        
        await store.ack(token)
```

For multi-process, use Postgres advisory locks or Redis.

-----

## FastAPI Integration

Minimal integration using FastAPI’s lifespan and dependency injection:

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from contextlib import asynccontextmanager
import httpx
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    store = SQLiteEventStore()
    await store.init()
    
    http = httpx.AsyncClient()
    
    app.state.store = store
    app.state.http = http
    
    # Start agent loop as background task
    app.state.agent_task = asyncio.create_task(
        run_agent(
            store=store,
            deps=ReflexDeps(event_store=store, http=http, db=None, scope="main"),
            filters=[keyword_filter(["error", "alert"])],
            trigger=alert_trigger,
        )
    )
    
    yield
    
    # Shutdown
    app.state.agent_task.cancel()
    await http.aclose()

app = FastAPI(lifespan=lifespan)

# Observability
import logfire
logfire.configure()
logfire.instrument_fastapi(app)
logfire.instrument_pydantic_ai()
logfire.instrument_httpx()

# Dependencies
async def get_store(request) -> EventStore:
    return request.app.state.store

async def get_deps(request, store: EventStore = Depends(get_store)) -> ReflexDeps:
    return ReflexDeps(
        event_store=store,
        http=request.app.state.http,
        db=None,
        scope="api",
    )

# Routes
@app.post("/events")
async def publish_event(event: Event, store: EventStore = Depends(get_store)):
    await store.publish(event)
    return {"id": event.id}

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    store: EventStore = Depends(get_store),
):
    await websocket.accept()
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
        pass
```

-----

## Project Structure

Flat and simple:

```
reflex/
├── src/
│   └── reflex/
│       ├── __init__.py
│       ├── py.typed
│       ├── events.py       # Event types, discriminated union
│       ├── store.py        # EventStore protocol, SQLiteEventStore
│       ├── context.py      # DecisionContext
│       ├── deps.py         # ReflexDeps
│       └── locks.py        # ScopedLocks
├── tests/
│   ├── test_events.py
│   ├── test_store.py
│   └── test_context.py
├── examples/
│   ├── simple_monitor.py
│   ├── chat_agent.py
│   └── multi_agent.py
├── pyproject.toml
└── README.md
```

-----

## Configuration

### pyproject.toml

```toml
[project]
name = "reflex"
version = "0.3.0"
description = "Real-time AI agent primitives for continuous perception-action loops"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.10",
    "pydantic-ai>=1.0",
    "sqlmodel>=0.0.22",
    "aiosqlite>=0.20",
    "httpx>=0.28",
    "logfire>=2.0",
]

[project.optional-dependencies]
api = [
    "fastapi>=0.115",
    "uvicorn>=0.32",
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
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

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "ASYNC", "TCH", "S"]

[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "strict"
reportMissingTypeStubs = false
reportUnknownMemberType = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

-----

## Implementation Plan

### Phase 1: Core Primitives (Week 1)

**Deliverables:**

- Event types with discriminated union
- SQLiteEventStore with async sessions
- DecisionContext
- ReflexDeps
- ScopedLocks

**Milestone:** Can store events, subscribe, ack/nack, and replay.

### Phase 2: Integration (Week 2)

**Deliverables:**

- FastAPI example with WebSocket
- Logfire instrumentation
- Basic PydanticAI agent example
- Documentation with patterns

**Milestone:** Working example that ingests WebSocket messages, filters, triggers an agent, and responds.

### Phase 3: Hardening (Week 3)

**Deliverables:**

- Comprehensive tests
- DLQ inspection utilities
- Replay debugging tools
- Performance benchmarks

**Milestone:** Production-ready library with test coverage >80%.

-----

## What Reflex Doesn’t Do

Explicit non-goals to keep the library focused:

- **No DSL.** Write Python, not YAML or custom syntax.
- **No combinators.** Use `asyncio.gather`, `tenacity`, standard control flow.
- **No topology classes.** Pipelines and hierarchies are just function calls.
- **No auto-wiring.** You explicitly connect components.
- **No distributed coordination.** Single-process by default. Use Redis/Postgres when you need it.
- **No model abstraction.** PydanticAI handles that.

-----

## Success Criteria

1. **Simplicity:** Core library under 500 lines of code.
1. **No magic:** A Python developer can read any example and understand it without docs.
1. **Type safety:** Full Pyright strict compliance.
1. **Performance:** EventStore handles 1000+ events/second.
1. **Observability:** Full Logfire trace from event ingestion to agent response.

-----

## Anti-Patterns to Avoid

1. **Blocking calls in async.** No `time.sleep()`, `requests`, sync database calls.
1. **Global mutable state.** Use `app.state` or pass dependencies explicitly.
1. **Over-abstraction.** If you’re writing a wrapper around `asyncio.gather`, stop.
1. **Framework thinking.** Users should feel like they’re writing an async Python app, not configuring a framework.

-----

## References

- [PydanticAI Documentation](https://ai.pydantic.dev/)
- [Pydantic v2 Documentation](https://docs.pydantic.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [Logfire Documentation](https://logfire.pydantic.dev/)