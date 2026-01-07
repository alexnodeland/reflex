# Reflex Development Plan

**Project:** Real-time AI Agent Template  
**Version:** 0.5.0  
**Timeline:** 6 Sprints (12 weeks)  
**Last Updated:** January 2026

-----

## Overview

This development plan breaks down the Reflex project into actionable phases, each with clear deliverables, acceptance criteria, and technical specifications. The plan follows a bottom-up approach: infrastructure first, then core abstractions, then the agent layer, and finally the API surface.

-----

## Table of Contents

1. [Phase 1: Project Scaffolding & Infrastructure](#phase-1-project-scaffolding--infrastructure)
1. [Phase 2: Database & Event Store](#phase-2-database--event-store)
1. [Phase 3: Core Domain Types](#phase-3-core-domain-types)
1. [Phase 4: Agent Loop & Processing](#phase-4-agent-loop--processing)
1. [Phase 5: API Layer & WebSocket Support](#phase-5-api-layer--websocket-support)
1. [Phase 6: Testing, CI/CD & Documentation](#phase-6-testing-cicd--documentation)
1. [Risk Register](#risk-register)
1. [Technical Decisions Log](#technical-decisions-log)

-----

## Phase 1: Project Scaffolding & Infrastructure

**Duration:** 1 week (Sprint 1)  
**Goal:** Establish project structure, development environment, and core tooling

### 1.1 Repository Setup

**Tasks:**

|Task                      |Description                                              |Estimate|
|--------------------------|---------------------------------------------------------|--------|
|Initialize repository     |Create Git repo with `.gitignore`, `LICENSE`, `README.md`|1h      |
|Configure `pyproject.toml`|Dependencies, build system, tool configs                 |2h      |
|Create directory structure|Follow PRD structure exactly                             |1h      |
|Add `py.typed` marker     |PEP 561 compliance for type checking                     |15m     |

**Directory Structure to Create:**

```
reflex/
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.dev
│   └── docker-compose.yml
├── src/
│   └── reflex/
│       ├── __init__.py
│       ├── py.typed
│       ├── config.py
│       ├── infra/
│       │   └── __init__.py
│       ├── core/
│       │   └── __init__.py
│       ├── agent/
│       │   └── __init__.py
│       └── api/
│           ├── __init__.py
│           └── routes/
│               └── __init__.py
├── tests/
│   └── conftest.py
├── scripts/
├── .github/
│   └── workflows/
├── .env.example
├── Makefile
└── README.md
```

**Deliverables:**

- [ ] Repository initialized with all directories
- [ ] `pyproject.toml` with all dependencies specified
- [ ] `.env.example` with documented variables
- [ ] `Makefile` with basic targets (`dev`, `test`, `lint`, `clean`)

### 1.2 Docker Configuration

**Tasks:**

|Task                        |Description                            |Estimate|
|----------------------------|---------------------------------------|--------|
|Create `Dockerfile.dev`     |Hot-reload development image           |2h      |
|Create `Dockerfile`         |Multi-stage production build           |2h      |
|Create `docker-compose.yml` |App + Postgres with health checks      |2h      |
|Test container orchestration|Verify startup, shutdown, volume mounts|1h      |

**Acceptance Criteria:**

- [ ] `docker compose up` starts both services within 30 seconds
- [ ] Hot reload works: file changes trigger server restart
- [ ] Postgres health check passes before app starts
- [ ] Graceful shutdown completes within 10 seconds
- [ ] Named volume persists database between restarts

**Implementation Notes:**

```yaml
# Key docker-compose.yml requirements
services:
  app:
    depends_on:
      db:
        condition: service_healthy  # Critical: wait for Postgres
    volumes:
      - ./src:/app/src  # Hot reload
    
  db:
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U reflex"]
      interval: 5s
      timeout: 5s
      retries: 5
```

### 1.3 Configuration Module

**File:** `src/reflex/config.py`

**Tasks:**

|Task                      |Description                         |Estimate|
|--------------------------|------------------------------------|--------|
|Implement `Settings` class|Pydantic-settings with all env vars |2h      |
|Add validation            |Ensure required fields, valid ranges|1h      |
|Write tests               |Test default values, env override   |1h      |

**Settings to Implement:**

|Setting                     |Type        |Default                   |Description                     |
|----------------------------|------------|--------------------------|--------------------------------|
|`database_url`              |`str`       |`postgresql+asyncpg://...`|Async Postgres connection string|
|`database_pool_size`        |`int`       |`5`                       |Connection pool size            |
|`database_pool_max_overflow`|`int`       |`10`                      |Max overflow connections        |
|`api_host`                  |`str`       |`0.0.0.0`                 |API bind host                   |
|`api_port`                  |`int`       |`8000`                    |API bind port                   |
|`api_reload`                |`bool`      |`False`                   |Enable hot reload               |
|`logfire_token`             |`str | None`|`None`                    |Logfire API token               |
|`log_level`                 |`str`       |`INFO`                    |Logging level                   |
|`openai_api_key`            |`str | None`|`None`                    |OpenAI API key                  |
|`default_model`             |`str`       |`openai:gpt-4o-mini`      |Default LLM model               |
|`event_max_attempts`        |`int`       |`3`                       |Max retry attempts              |
|`event_retry_base_delay`    |`float`     |`1.0`                     |Base retry delay (seconds)      |
|`event_retry_max_delay`     |`float`     |`60.0`                    |Max retry delay (seconds)       |
|`environment`               |`str`       |`development`             |Runtime environment             |
|`version`                   |`str`       |`0.1.0`                   |Application version             |

**Acceptance Criteria:**

- [ ] All settings load from environment variables
- [ ] `.env` file is read when present
- [ ] Invalid values raise clear validation errors
- [ ] Singleton `settings` instance exported from module

### 1.4 Observability Setup

**File:** `src/reflex/infra/observability.py`

**Tasks:**

|Task                                 |Description              |Estimate|
|-------------------------------------|-------------------------|--------|
|Implement `configure_observability()`|Logfire initialization   |1h      |
|Implement `instrument_app()`         |FastAPI + integrations   |2h      |
|Test trace propagation               |Verify end-to-end tracing|1h      |

**Integrations to Enable:**

- `logfire.instrument_fastapi(app)` — HTTP request tracing
- `logfire.instrument_pydantic_ai()` — Agent call tracing with token usage
- `logfire.instrument_asyncpg()` — Database query tracing
- `logfire.instrument_httpx()` — Outgoing HTTP request tracing

**Acceptance Criteria:**

- [ ] Traces appear in Logfire dashboard (when token configured)
- [ ] Console output in development mode
- [ ] Service name, version, environment correctly tagged
- [ ] Spans nest correctly (HTTP → Agent → DB)

### Phase 1 Exit Criteria

- [ ] `docker compose up` brings up healthy system
- [ ] `make lint` passes with ruff
- [ ] `make type-check` passes with pyright (strict mode)
- [ ] Configuration loads correctly from `.env`
- [ ] Logfire console output shows structured logs

-----

## Phase 2: Database & Event Store

**Duration:** 2 weeks (Sprints 2-3)  
**Goal:** Implement persistent event storage with real-time subscriptions

### 2.1 Database Module

**File:** `src/reflex/infra/database.py`

**Tasks:**

|Task                       |Description                      |Estimate|
|---------------------------|---------------------------------|--------|
|Create async engine        |SQLAlchemy async with pooling    |2h      |
|Create session factory     |`expire_on_commit=False` critical|1h      |
|Create raw asyncpg pool    |For LISTEN/NOTIFY                |2h      |
|Implement `init_database()`|Table creation                   |1h      |
|Write tests                |Connection, session lifecycle    |2h      |

**Critical Implementation Details:**

```python
# Session factory MUST have expire_on_commit=False
SessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevents implicit I/O after commit
)
```

**Acceptance Criteria:**

- [ ] Connection pool respects size limits
- [ ] `pool_pre_ping=True` validates connections
- [ ] Sessions don’t trigger lazy loads after commit
- [ ] Raw pool separate from SQLAlchemy for LISTEN/NOTIFY

### 2.2 Event Record Model

**File:** `src/reflex/infra/store.py` (partial)

**Tasks:**

|Task                         |Description                |Estimate|
|-----------------------------|---------------------------|--------|
|Define `EventRecord` SQLModel|All fields with indices    |2h      |
|Create migration script      |`scripts/migrate.py`       |1h      |
|Test schema creation         |Verify indices, constraints|1h      |

**Schema Definition:**

|Column        |Type       |Index|Description                                |
|--------------|-----------|-----|-------------------------------------------|
|`id`          |`VARCHAR`  |PK   |Event UUID                                 |
|`type`        |`VARCHAR`  |Yes  |Event type discriminator                   |
|`source`      |`VARCHAR`  |Yes  |Event source identifier                    |
|`timestamp`   |`TIMESTAMP`|Yes  |Event creation time                        |
|`payload`     |`TEXT`     |No   |JSON-serialized event                      |
|`status`      |`VARCHAR`  |Yes  |`pending`, `processing`, `completed`, `dlq`|
|`attempts`    |`INTEGER`  |No   |Processing attempt count                   |
|`error`       |`TEXT`     |No   |Last error message                         |
|`created_at`  |`TIMESTAMP`|No   |Record creation time                       |
|`processed_at`|`TIMESTAMP`|No   |Successful processing time                 |

**Status State Machine:**

```
pending → processing → completed
              ↓
           failed
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
 pending            dlq (max attempts)
 (retry)
```

### 2.3 EventStore Implementation

**File:** `src/reflex/infra/store.py`

**Tasks:**

|Task                     |Description               |Estimate|
|-------------------------|--------------------------|--------|
|Implement `publish()`    |Insert + NOTIFY           |3h      |
|Implement `subscribe()`  |LISTEN + claim events     |6h      |
|Implement `ack()`        |Mark completed            |1h      |
|Implement `nack()`       |Mark failed, retry or DLQ |2h      |
|Implement `replay()`     |Historical event iteration|2h      |
|Implement `dlq_list()`   |List DLQ events           |1h      |
|Implement `dlq_retry()`  |Move from DLQ to pending  |1h      |
|Write comprehensive tests|All methods, edge cases   |4h      |

**Method Signatures:**

```python
class EventStore:
    async def publish(self, event: Event) -> None
    async def subscribe(
        self,
        event_types: list[str] | None = None,
        batch_size: int = 100,
    ) -> AsyncIterator[tuple[Event, str]]
    async def ack(self, token: str) -> None
    async def nack(self, token: str, error: str | None = None) -> None
    async def replay(
        self,
        start: datetime,
        end: datetime | None = None,
        event_types: list[str] | None = None,
    ) -> AsyncIterator[Event]
    async def dlq_list(self, limit: int = 100) -> list[Event]
    async def dlq_retry(self, event_id: str) -> bool
```

**Critical Implementation: Subscribe with LISTEN/NOTIFY**

```python
async def subscribe(self, event_types=None, batch_size=100):
    async with self.pool.acquire() as conn:
        await conn.execute("LISTEN events")
        
        while True:
            # 1. Claim pending events with FOR UPDATE SKIP LOCKED
            # 2. Yield claimed events
            # 3. If no events, wait for NOTIFY with timeout
            # 4. Loop
```

**Acceptance Criteria:**

- [ ] Events persist across container restarts
- [ ] NOTIFY triggers subscriber immediately (< 100ms)
- [ ] Concurrent subscribers don’t claim same event
- [ ] Failed events retry with exponential backoff
- [ ] Events exceeding `max_attempts` move to DLQ
- [ ] Replay returns events in timestamp order
- [ ] All operations traced in Logfire

### 2.4 Scoped Locking

**File:** `src/reflex/infra/locks.py`

**Tasks:**

|Task                                |Description          |Estimate|
|------------------------------------|---------------------|--------|
|Implement `ScopedLocks` class       |In-memory async locks|2h      |
|Document Postgres/Redis alternatives|For multi-process    |1h      |
|Write tests                         |Concurrent access    |1h      |

**Interface:**

```python
class ScopedLocks:
    @asynccontextmanager
    async def acquire(self, scope: str) -> AsyncIterator[None]
    def is_locked(self, scope: str) -> bool
```

**Acceptance Criteria:**

- [ ] Only one coroutine holds lock for a scope
- [ ] Lock released even on exception
- [ ] Different scopes don’t block each other

### Phase 2 Exit Criteria

- [ ] Events persist to Postgres
- [ ] LISTEN/NOTIFY subscription works
- [ ] `FOR UPDATE SKIP LOCKED` prevents duplicate processing
- [ ] Retry with backoff functions correctly
- [ ] DLQ captures exhausted events
- [ ] Replay utility works end-to-end
- [ ] All store methods have tests with >90% coverage

-----

## Phase 3: Core Domain Types

**Duration:** 1 week (Sprint 4)  
**Goal:** Define event types, decision context, and dependency injection

### 3.1 Event Types

**File:** `src/reflex/core/events.py`

**Tasks:**

|Task                      |Description                      |Estimate|
|--------------------------|---------------------------------|--------|
|Define `EventMeta`        |Trace context fields             |1h      |
|Define `BaseEvent`        |Shared event fields              |1h      |
|Define built-in events    |WebSocket, HTTP, Timer, Lifecycle|2h      |
|Create discriminated union|`Event` type alias               |1h      |
|Write validation tests    |All event types                  |2h      |

**Built-in Event Types:**

|Type            |Discriminator |Key Fields                         |
|----------------|--------------|-----------------------------------|
|`WebSocketEvent`|`ws.message`  |`connection_id`, `content`         |
|`HTTPEvent`     |`http.request`|`method`, `path`, `headers`, `body`|
|`TimerEvent`    |`timer.tick`  |`timer_name`, `tick_count`         |
|`LifecycleEvent`|`lifecycle`   |`action`, `details`                |

**Discriminated Union Pattern:**

```python
Event = Annotated[
    Union[WebSocketEvent, HTTPEvent, TimerEvent, LifecycleEvent],
    Field(discriminator="type")
]
```

**Acceptance Criteria:**

- [ ] Validation is O(1) via discriminator
- [ ] Invalid `type` values raise clear errors
- [ ] All events serialize to/from JSON
- [ ] `EventMeta` propagates trace context

### 3.2 Decision Context

**File:** `src/reflex/core/context.py`

**Tasks:**

|Task                       |Description                     |Estimate|
|---------------------------|--------------------------------|--------|
|Implement `DecisionContext`|Pydantic model with helpers     |3h      |
|Implement helper methods   |`add`, `window`, `of_type`, etc.|2h      |
|Write tests                |All methods                     |2h      |

**Method Inventory:**

|Method                 |Description                    |
|-----------------------|-------------------------------|
|`add(event)`           |Append event to context        |
|`window(seconds)`      |Get events within time window  |
|`of_type(*types)`      |Filter by event type           |
|`since_last_action()`  |Events since last trigger fired|
|`count_by_type()`      |Aggregate counts               |
|`summarize(max_events)`|Human-readable summary for LLM |
|`clear()`              |Reset after action taken       |
|`mark_action()`        |Mark action without clearing   |

**Acceptance Criteria:**

- [ ] Context accumulates events correctly
- [ ] Time window filtering works with edge cases
- [ ] `summarize()` produces useful LLM context
- [ ] `clear()` resets all state

### 3.3 Dependencies

**File:** `src/reflex/core/deps.py`

**Tasks:**

|Task                         |Description        |Estimate|
|-----------------------------|-------------------|--------|
|Define `ReflexDeps` dataclass|Core dependencies  |1h      |
|Document extension pattern   |Adding custom deps |30m     |
|Write integration test       |Deps flow to agents|1h      |

**Core Dependencies:**

```python
@dataclass
class ReflexDeps:
    store: EventStore
    http: httpx.AsyncClient
    db: AsyncSession
    scope: str
```

**Acceptance Criteria:**

- [ ] Deps accessible via `RunContext[ReflexDeps]` in tools
- [ ] All core dependencies present
- [ ] Easy to extend with custom dependencies

### Phase 3 Exit Criteria

- [ ] All event types validate correctly
- [ ] Discriminated union performs O(1) dispatch
- [ ] `DecisionContext` helpers work correctly
- [ ] `ReflexDeps` integrates with PydanticAI
- [ ] Type checking passes with strict mode

-----

## Phase 4: Agent Loop & Processing

**Duration:** 2 weeks (Sprints 5-6)  
**Goal:** Implement filters, triggers, PydanticAI agents, and the main loop

### 4.1 Filter Functions

**File:** `src/reflex/agent/filters.py`

**Tasks:**

|Task                         |Description                               |Estimate|
|-----------------------------|------------------------------------------|--------|
|Define `Filter` type alias   |`Callable[[Event, DecisionContext], bool]`|30m     |
|Implement `keyword_filter`   |Match any keyword in payload              |1h      |
|Implement `event_type_filter`|Match by event type                       |30m     |
|Implement `rate_limit_filter`|Cap events per window                     |1h      |
|Implement `dedupe_filter`    |Deduplicate by key                        |1h      |
|Implement `all_filters`      |AND composition                           |30m     |
|Implement `any_filter`       |OR composition                            |30m     |
|Write tests                  |All filters                               |2h      |

**Filter Composition Example:**

```python
# Combine filters with standard Python
my_filter = all_filters(
    event_type_filter("error", "exception"),
    rate_limit_filter(100, 60),
    dedupe_filter(lambda e: e.id),
)
```

**Acceptance Criteria:**

- [ ] Filters are pure functions (no I/O)
- [ ] Filters are fast (microseconds)
- [ ] Composition works correctly
- [ ] Easy to add custom filters

### 4.2 Trigger Functions

**File:** `src/reflex/agent/triggers.py`

**Tasks:**

|Task                                |Description                                              |Estimate|
|------------------------------------|---------------------------------------------------------|--------|
|Define `Trigger` type alias         |`Callable[[DecisionContext, ReflexDeps], Awaitable[Any]]`|30m     |
|Implement `error_threshold_trigger` |Alert on error count                                     |3h      |
|Implement `periodic_summary_trigger`|Summarize after N events                                 |2h      |
|Implement `immediate_trigger`       |Fire on every event                                      |1h      |
|Write tests                         |Mock agents, verify logic                                |3h      |

**Trigger Contract:**

```python
async def my_trigger(
    ctx: DecisionContext,
    deps: ReflexDeps,
) -> Any | None:
    """
    Returns:
        - Non-None value: Trigger fired, action taken
        - None: Trigger condition not met
    """
```

**Acceptance Criteria:**

- [ ] Triggers can call PydanticAI agents
- [ ] Return value indicates if trigger fired
- [ ] Context is cleared when trigger fires
- [ ] Errors propagate correctly

### 4.3 PydanticAI Agents

**File:** `src/reflex/agent/agents.py`

**Tasks:**

|Task                          |Description                                                             |Estimate|
|------------------------------|------------------------------------------------------------------------|--------|
|Create `AlertResponse` model  |Structured alert output                                                 |1h      |
|Create `alert_agent`          |Alert generation agent                                                  |3h      |
|Add tools to `alert_agent`    |`get_recent_events`, `send_slack_notification`, `create_incident_ticket`|4h      |
|Create `SummaryResponse` model|Structured summary output                                               |1h      |
|Create `summary_agent`        |Event summarization agent                                               |2h      |
|Write tests                   |Mock LLM responses                                                      |3h      |

**Agent Pattern:**

```python
alert_agent = Agent(
    settings.default_model,
    deps_type=ReflexDeps,
    result_type=AlertResponse,
    system_prompt="...",
)

@alert_agent.tool
async def get_recent_events(
    ctx: RunContext[ReflexDeps],
    event_type: str | None = None,
    hours: int = 1,
) -> str:
    # Access deps via ctx.deps
    ...
```

**Tool Inventory:**

|Tool                     |Agent|Description                      |
|-------------------------|-----|---------------------------------|
|`get_recent_events`      |Alert|Fetch historical events          |
|`send_slack_notification`|Alert|Post to Slack webhook            |
|`create_incident_ticket` |Alert|Create ticket in ticketing system|

**Acceptance Criteria:**

- [ ] Agents return structured Pydantic models
- [ ] Tools access dependencies correctly
- [ ] System prompts are clear and actionable
- [ ] Logfire traces agent calls with token usage

### 4.4 Agent Loop

**File:** `src/reflex/agent/loop.py`

**Tasks:**

|Task                      |Description                 |Estimate|
|--------------------------|----------------------------|--------|
|Implement `run_agent_loop`|Main processing loop        |4h      |
|Handle graceful shutdown  |`asyncio.CancelledError`    |1h      |
|Add Logfire spans         |Trace each event            |1h      |
|Write tests               |Happy path, errors, shutdown|4h      |

**Loop Pseudocode:**

```
1. Create DecisionContext for scope
2. Subscribe to EventStore
3. For each (event, token):
   a. Apply filters (fast, sync)
   b. If relevant:
      - Add to context
      - Evaluate trigger (may call LLM)
      - If trigger fires:
        - Clear context
   c. Ack event
   d. On error: nack event
4. On cancellation: exit gracefully
```

**Acceptance Criteria:**

- [ ] Loop processes events continuously
- [ ] Filters reject irrelevant events quickly
- [ ] Context accumulates between triggers
- [ ] Graceful shutdown completes cleanly
- [ ] Errors are logged and events nacked
- [ ] Full trace from HTTP to DB visible in Logfire

### 4.5 Alternative Loop Patterns (Documentation)

**Tasks:**

|Task                      |Description            |Estimate|
|--------------------------|-----------------------|--------|
|Document real-time pattern|Trigger on every event |1h      |
|Document batch pattern    |Accumulate then process|1h      |
|Document parallel pattern |Multiple workers       |1h      |

**Patterns to Document:**

- Real-time response (trigger on every event)
- Batch processing (accumulate to threshold)
- Multiple concurrent consumers
- Supervisor/worker delegation

### Phase 4 Exit Criteria

- [ ] Filters work correctly and compose
- [ ] Triggers integrate with PydanticAI agents
- [ ] Agent tools access dependencies
- [ ] Main loop runs continuously
- [ ] Graceful shutdown works
- [ ] End-to-end tracing visible in Logfire
- [ ] Test coverage >85%

-----

## Phase 5: API Layer & WebSocket Support

**Duration:** 1.5 weeks (Sprints 7-8)  
**Goal:** Implement FastAPI application with routes and WebSocket handling

### 5.1 FastAPI Application

**File:** `src/reflex/api/app.py`

**Tasks:**

|Task                      |Description                  |Estimate|
|--------------------------|-----------------------------|--------|
|Implement lifespan handler|Startup/shutdown sequence    |4h      |
|Configure middleware      |Observability instrumentation|1h      |
|Include routers           |Health, events, WebSocket    |1h      |
|Write integration tests   |Full app lifecycle           |3h      |

**Lifespan Sequence:**

```
Startup:
1. configure_observability()
2. init_database()
3. create_raw_pool()
4. Create httpx.AsyncClient
5. Create EventStore
6. Create ScopedLocks
7. Start agent loop as background task

Shutdown:
1. Cancel agent loop (wait for completion)
2. Close httpx client
3. Close raw pool
4. Dispose engine
```

**Acceptance Criteria:**

- [ ] All resources initialized in correct order
- [ ] Dependencies available in `app.state`
- [ ] Background task starts and stops cleanly
- [ ] Observability instruments all layers

### 5.2 Health Routes

**File:** `src/reflex/api/routes/health.py`

**Tasks:**

|Task               |Description            |Estimate|
|-------------------|-----------------------|--------|
|Implement `/health`|Basic liveness check   |30m     |
|Implement `/ready` |Readiness with DB check|1h      |
|Write tests        |Both endpoints         |1h      |

**Endpoints:**

|Endpoint |Method|Purpose        |Returns                     |
|---------|------|---------------|----------------------------|
|`/health`|GET   |Liveness probe |`{"status": "healthy"}`     |
|`/ready` |GET   |Readiness probe|`{"status": "ready"}` or 503|

**Acceptance Criteria:**

- [ ] `/health` always returns 200 if process is running
- [ ] `/ready` returns 503 if DB unreachable
- [ ] Kubernetes probes can use these endpoints

### 5.3 Event Routes

**File:** `src/reflex/api/routes/events.py`

**Tasks:**

|Task                                   |Description    |Estimate|
|---------------------------------------|---------------|--------|
|Implement `POST /events`               |Publish event  |2h      |
|Implement `GET /events/dlq`            |List DLQ       |1h      |
|Implement `POST /events/dlq/{id}/retry`|Retry DLQ event|1h      |
|Write tests                            |All endpoints  |2h      |

**Endpoints:**

|Endpoint                |Method|Purpose      |Request Body|Response                |
|------------------------|------|-------------|------------|------------------------|
|`/events`               |POST  |Publish event|`Event`     |`{"id", "status"}`      |
|`/events/dlq`           |GET   |List DLQ     |—           |`{"count", "events"}`   |
|`/events/dlq/{id}/retry`|POST  |Retry event  |—           |`{"status", "event_id"}`|

**Acceptance Criteria:**

- [ ] Events validate against discriminated union
- [ ] Invalid events return 422 with details
- [ ] DLQ listing paginated via `limit` param
- [ ] Retry returns 404 if event not in DLQ

### 5.4 WebSocket Routes

**File:** `src/reflex/api/routes/ws.py`

**Tasks:**

|Task                        |Description                |Estimate|
|----------------------------|---------------------------|--------|
|Implement `/ws/{client_id}` |WebSocket handler          |3h      |
|Handle connection lifecycle |Accept, receive, disconnect|1h      |
|Publish events from messages|Create `WebSocketEvent`    |1h      |
|Write tests                 |Connection, messaging      |2h      |

**WebSocket Protocol:**

```
Client → Server: {"content": "message text"}
Server → Client: {"ack": "event_id"}
```

**Acceptance Criteria:**

- [ ] Connections accepted with client ID
- [ ] Messages create `WebSocketEvent` with correct source
- [ ] Acknowledgments sent for each message
- [ ] Disconnections logged and handled gracefully
- [ ] Multiple concurrent connections supported

### 5.5 API Dependencies

**File:** `src/reflex/api/deps.py`

**Tasks:**

|Task                 |Description                   |Estimate|
|---------------------|------------------------------|--------|
|Implement `get_store`|Extract from app.state        |30m     |
|Implement `get_http` |Extract from app.state        |30m     |
|Implement `get_deps` |Create `ReflexDeps` for routes|1h      |
|Write tests          |Dependency injection          |1h      |

**Acceptance Criteria:**

- [ ] Dependencies injectable via FastAPI `Depends`
- [ ] Each request gets fresh DB session
- [ ] Shared resources (store, http) reused

### Phase 5 Exit Criteria

- [ ] API starts and shuts down correctly
- [ ] Health endpoints pass Kubernetes probes
- [ ] Events can be published via HTTP
- [ ] DLQ management works via API
- [ ] WebSocket connections work end-to-end
- [ ] All routes have tests
- [ ] OpenAPI docs generated correctly

-----

## Phase 6: Testing, CI/CD & Documentation

**Duration:** 1.5 weeks (Sprints 9-10)  
**Goal:** Comprehensive testing, CI/CD pipeline, and documentation

### 6.1 Test Suite

**Directory:** `tests/`

**Tasks:**

|Task                      |Description         |Estimate|
|--------------------------|--------------------|--------|
|Configure `pytest-asyncio`|Async test support  |1h      |
|Create fixtures           |DB, store, deps, app|4h      |
|Write unit tests          |All modules         |8h      |
|Write integration tests   |End-to-end flows    |6h      |
|Configure coverage        |Target 90%          |1h      |

**Test Categories:**

|Category          |Location               |Coverage Target|
|------------------|-----------------------|---------------|
|Unit: Config      |`tests/test_config.py` |100%           |
|Unit: Events      |`tests/test_events.py` |100%           |
|Unit: Context     |`tests/test_context.py`|100%           |
|Unit: Filters     |`tests/test_filters.py`|100%           |
|Integration: Store|`tests/test_store.py`  |90%            |
|Integration: Agent|`tests/test_agent.py`  |85%            |
|Integration: API  |`tests/test_api.py`    |90%            |

**Key Fixtures:**

```python
@pytest.fixture
async def db_pool():
    """Create test database and pool."""
    
@pytest.fixture
async def store(db_pool):
    """Create EventStore with test database."""
    
@pytest.fixture
async def deps(store):
    """Create ReflexDeps for testing."""
    
@pytest.fixture
async def app(store):
    """Create test FastAPI application."""
    
@pytest.fixture
async def client(app):
    """Create async test client."""
```

**Acceptance Criteria:**

- [ ] All tests pass in CI
- [ ] Coverage >90% overall
- [ ] No flaky tests
- [ ] Tests run in <60 seconds

### 6.2 CI Pipeline

**File:** `.github/workflows/ci.yml`

**Tasks:**

|Task                       |Description         |Estimate|
|---------------------------|--------------------|--------|
|Configure workflow triggers|Push, PR            |30m     |
|Set up Postgres service    |Health checks       |1h      |
|Add lint job               |ruff check          |30m     |
|Add type check job         |pyright strict      |30m     |
|Add test job               |pytest with coverage|1h      |
|Add build job              |Docker image        |1h      |
|Configure caching          |pip, Docker layers  |1h      |

**Pipeline Stages:**

```
Push/PR
  ├── Lint (ruff check)
  ├── Type Check (pyright)
  └── Test (pytest + Postgres service)
        └── Coverage upload

Main Branch Only:
  └── Build (Docker image)
```

**Acceptance Criteria:**

- [ ] PRs blocked on lint/type/test failures
- [ ] Coverage reported to codecov
- [ ] Docker image builds on main branch
- [ ] Pipeline completes in <5 minutes

### 6.3 Utility Scripts

**Directory:** `scripts/`

**Tasks:**

|Task                     |Description         |Estimate|
|-------------------------|--------------------|--------|
|Implement `migrate.py`   |Database migration  |2h      |
|Implement `replay.py`    |Event replay utility|3h      |
|Implement `dlq.py`       |DLQ management CLI  |2h      |
|Write usage documentation|README sections     |1h      |

**Script Inventory:**

|Script      |Purpose                 |Usage                               |
|------------|------------------------|------------------------------------|
|`migrate.py`|Create/update tables    |`python scripts/migrate.py`         |
|`replay.py` |Replay historical events|`python scripts/replay.py --last 1h`|
|`dlq.py`    |Manage dead-letter queue|`python scripts/dlq.py list`        |

**Acceptance Criteria:**

- [ ] Scripts work in Docker containers
- [ ] Clear help messages (`--help`)
- [ ] Error handling with useful messages

### 6.4 Documentation

**Files:** `README.md`, inline documentation

**Tasks:**

|Task                  |Description                   |Estimate|
|----------------------|------------------------------|--------|
|Write README          |Overview, quickstart, examples|4h      |
|Document architecture |Diagrams, design decisions    |2h      |
|Write docstrings      |All public APIs               |3h      |
|Create CONTRIBUTING.md|Development workflow          |1h      |

**README Sections:**

1. Overview / What is Reflex
1. Quick Start (3-step)
1. Architecture Overview
1. Project Structure (what to keep/replace)
1. Configuration Reference
1. API Reference
1. Development Guide
1. Deployment Guide
1. Troubleshooting

**Acceptance Criteria:**

- [ ] New developer can start in <5 minutes
- [ ] All public APIs documented
- [ ] Architecture diagrams present
- [ ] Common issues covered in troubleshooting

### Phase 6 Exit Criteria

- [ ] Test coverage >90%
- [ ] CI pipeline passes on all PRs
- [ ] Docker image builds successfully
- [ ] README enables quick start
- [ ] All scripts functional
- [ ] Code documented with docstrings

-----

## Risk Register

|Risk                              |Impact|Probability|Mitigation                                |
|----------------------------------|------|-----------|------------------------------------------|
|Postgres LISTEN/NOTIFY scalability|High  |Medium     |Document Redis alternative for high-volume|
|PydanticAI breaking changes       |Medium|Low        |Pin dependency version, monitor releases  |
|Logfire availability              |Low   |Low        |Graceful degradation, console fallback    |
|Async complexity                  |Medium|Medium     |Comprehensive tests, ruff ASYNC rules     |
|Docker build times                |Low   |Medium     |Multi-stage builds, layer caching         |
|Test flakiness                    |Medium|Medium     |Proper async cleanup, isolated DB         |

-----

## Technical Decisions Log

|Decision                     |Rationale                            |Alternatives Considered                       |
|-----------------------------|-------------------------------------|----------------------------------------------|
|PostgreSQL for events        |LISTEN/NOTIFY, ACID, proven scale    |Redis Streams (less durable), Kafka (overkill)|
|asyncpg for LISTEN/NOTIFY    |SQLAlchemy doesn’t expose this       |psycopg3 (newer, less tested)                 |
|Pydantic discriminated unions|O(1) validation, type safety         |Tagged unions, manual dispatch                |
|In-memory locks              |Simple, sufficient for single-process|Postgres advisory locks, Redis locks          |
|SQLModel over SQLAlchemy     |Pydantic integration, simpler models |Raw SQLAlchemy (more verbose)                 |
|`expire_on_commit=False`     |Prevents implicit I/O in async       |Explicit refresh (more code)                  |
|Logfire over OpenTelemetry   |Better PydanticAI integration        |OTEL (more generic, less integrated)          |
|uv for package management    |Fast, reliable                       |pip (slower), poetry (heavier)                |

-----

## Sprint Summary

|Sprint|Duration |Focus      |Key Deliverables                 |
|------|---------|-----------|---------------------------------|
|1     |1 week   |Scaffolding|Project structure, Docker, config|
|2-3   |2 weeks  |Database   |EventStore, LISTEN/NOTIFY, DLQ   |
|4     |1 week   |Core Types |Events, context, dependencies    |
|5-6   |2 weeks  |Agent      |Filters, triggers, agents, loop  |
|7-8   |1.5 weeks|API        |FastAPI, routes, WebSocket       |
|9-10  |1.5 weeks|Quality    |Tests, CI/CD, documentation      |

**Total Timeline:** 10 weeks (12 with buffer)

-----

## Definition of Done

A feature is complete when:

1. **Code complete** — Implementation matches specification
1. **Type safe** — Pyright strict mode passes
1. **Linted** — ruff check passes with no warnings
1. **Tested** — Unit and integration tests with >90% coverage
1. **Documented** — Docstrings on public APIs
1. **Reviewed** — PR approved by at least one reviewer
1. **Traced** — Logfire spans for observability
1. **Merged** — CI pipeline green, merged to main

-----

## Appendix: Dependency Versions

```toml
[project.dependencies]
pydantic = ">=2.10"
pydantic-ai = ">=1.0"
pydantic-settings = ">=2.0"
fastapi = ">=0.115"
uvicorn = { version = ">=0.32", extras = ["standard"] }
sqlmodel = ">=0.0.22"
sqlalchemy = { version = ">=2.0", extras = ["asyncio"] }
asyncpg = ">=0.30"
httpx = ">=0.28"
logfire = ">=2.0"
tenacity = ">=9.0"

[project.optional-dependencies.dev]
pytest = ">=8.0"
pytest-asyncio = ">=0.24"
pytest-cov = ">=6.0"
ruff = ">=0.8"
pyright = ">=1.1.390"
```

-----

## Appendix: Development Commands Reference

```bash
# Start development environment
make dev                    # docker compose up
make dev-build              # docker compose up --build
make dev-down               # docker compose down

# Code quality
make lint                   # ruff check
make lint-fix               # ruff check --fix
make format                 # ruff format
make type-check             # pyright strict

# Testing
make test                   # pytest -v
make test-cov               # pytest --cov with HTML report

# Database
make migrate                # Run migrations
make db-shell               # Connect to Postgres

# Utilities
make replay ARGS="--last 1h"  # Replay events
make dlq                      # List DLQ events
make logs                     # Follow app logs
make shell                    # Shell into app container

# Cleanup
make clean                  # Remove containers, caches
```