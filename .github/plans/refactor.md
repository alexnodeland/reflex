# Reflex Refactoring Plan

> A comprehensive plan to address architectural issues, improve abstractions, and enhance developer experience.

## Executive Summary

The current implementation is a solid MVP but has issues that will cause problems at scale:
- SQL injection risk in event filtering
- Global mutable state making testing difficult
- Single-process locks that fail silently in distributed deployments
- Inconsistent APIs (two filter patterns)
- Tight coupling requiring core changes for extensibility

This plan addresses these issues in prioritized phases.

---

## Phase 1: Critical Security & Correctness (Priority: CRITICAL)

### 1.1 Fix SQL Injection Risk in EventStore

**File:** `src/reflex/infra/store.py`

**Current Problem (lines 153-154):**
```python
types_str = ",".join(f"'{t}'" for t in event_types)
type_filter = f"AND type IN ({types_str})"  # String interpolation!
```

**Solution:** Use parameterized queries with PostgreSQL array syntax.

```python
# Before
if event_types:
    types_str = ",".join(f"'{t}'" for t in event_types)
    type_filter = f"AND type IN ({types_str})"

query = text(f"""
    SELECT ... WHERE status = 'pending' {type_filter}
""")

# After
query = text("""
    SELECT ...
    WHERE status = 'pending'
        AND (:event_types IS NULL OR type = ANY(:event_types))
""")
params = {"event_types": event_types, "batch_size": batch_size}
```

**Files to modify:**
- `src/reflex/infra/store.py` - `subscribe()`, `replay()` methods

**Tests to add:**
- `tests/test_store.py` - Test with malicious event type strings

---

### 1.2 Add Distributed Lock Support (or Fail Loudly)

**File:** `src/reflex/infra/locks.py`

**Current Problem:** In-memory locks silently fail in multi-process deployments.

**Solution:** Create abstract interface with implementations, add runtime warning.

```python
# src/reflex/infra/locks.py

from abc import ABC, abstractmethod
import warnings

class LockBackend(ABC):
    """Abstract lock backend interface."""

    @abstractmethod
    async def acquire(self, scope: str, timeout: float | None = None) -> bool:
        """Acquire lock for scope. Returns True if acquired."""
        ...

    @abstractmethod
    async def release(self, scope: str) -> None:
        """Release lock for scope."""
        ...

    @abstractmethod
    async def is_locked(self, scope: str) -> bool:
        """Check if scope is locked."""
        ...


class InMemoryLockBackend(LockBackend):
    """In-memory locks for single-process deployments.

    WARNING: These locks do NOT work across multiple processes.
    For distributed deployments, use PostgresLockBackend.
    """

    def __init__(self, warn_on_init: bool = True) -> None:
        if warn_on_init:
            warnings.warn(
                "InMemoryLockBackend only works for single-process deployments. "
                "For Kubernetes/multi-replica deployments, configure PostgresLockBackend.",
                UserWarning,
                stacklevel=2,
            )
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    # ... implementation


class PostgresLockBackend(LockBackend):
    """Distributed locks using PostgreSQL advisory locks.

    Safe for multi-process and distributed deployments.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def acquire(self, scope: str, timeout: float | None = None) -> bool:
        lock_id = self._scope_to_lock_id(scope)
        async with self._pool.acquire() as conn:
            if timeout:
                result = await conn.fetchval(
                    "SELECT pg_try_advisory_lock($1)", lock_id
                )
            else:
                await conn.execute("SELECT pg_advisory_lock($1)", lock_id)
                result = True
            return result

    async def release(self, scope: str) -> None:
        lock_id = self._scope_to_lock_id(scope)
        async with self._pool.acquire() as conn:
            await conn.execute("SELECT pg_advisory_unlock($1)", lock_id)

    def _scope_to_lock_id(self, scope: str) -> int:
        """Convert scope string to integer lock ID."""
        return hash(scope) & 0x7FFFFFFF  # Positive 32-bit int


class ScopedLocks:
    """High-level scoped lock manager."""

    def __init__(self, backend: LockBackend) -> None:
        self._backend = backend

    @asynccontextmanager
    async def __call__(self, scope: str) -> AsyncIterator[None]:
        await self._backend.acquire(scope)
        try:
            yield
        finally:
            await self._backend.release(scope)
```

**Configuration addition (`src/reflex/config.py`):**
```python
lock_backend: Literal["memory", "postgres"] = "memory"
```

**Files to modify:**
- `src/reflex/infra/locks.py` - Complete rewrite
- `src/reflex/config.py` - Add `lock_backend` setting
- `src/reflex/api/app.py` - Initialize correct backend based on config

**Tests to add:**
- `tests/test_locks.py` - Test both backends
- `tests/test_locks_postgres.py` - Integration test for advisory locks

---

## Phase 2: Eliminate Global Mutable State (Priority: HIGH)

### 2.1 Make Settings Injectable

**Current Problem:** `settings = Settings()` is a global singleton.

**Solution:** Pass settings as dependency, keep singleton as convenience default.

```python
# src/reflex/config.py

class Settings(BaseSettings):
    # ... existing fields
    pass

# Default instance for convenience (can be overridden)
_default_settings: Settings | None = None

def get_settings() -> Settings:
    """Get settings instance. Creates default if not configured."""
    global _default_settings
    if _default_settings is None:
        _default_settings = Settings()
    return _default_settings

def configure_settings(settings: Settings) -> None:
    """Configure custom settings (useful for testing)."""
    global _default_settings
    _default_settings = settings
```

**Files to modify:**
- `src/reflex/config.py` - Add `get_settings()` and `configure_settings()`
- All files importing `settings` - Change to use `get_settings()` or accept as parameter

---

### 2.2 Make Trigger Registry Injectable

**Current Problem:** Global `_registry = TriggerRegistry()` with module-level functions.

**Solution:** Pass registry as dependency to agent loop.

```python
# src/reflex/agent/triggers.py

class TriggerRegistry:
    """Registry for event triggers."""

    def __init__(self) -> None:
        self._triggers: dict[str, Trigger] = {}

    # ... existing methods

# Remove global instance and module-level functions
# Instead, create registry in app.py and pass to agent loop

# src/reflex/api/app.py
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # ... existing setup

    # Create trigger registry
    trigger_registry = TriggerRegistry()
    app.state.trigger_registry = trigger_registry

    # Pass to agent loop
    if settings.environment != "test":
        supervisor_task = asyncio.create_task(
            supervised_agent_loop(store, trigger_registry)
        )
```

**Files to modify:**
- `src/reflex/agent/triggers.py` - Remove global state
- `src/reflex/agent/loop.py` - Accept registry as parameter
- `src/reflex/api/app.py` - Create and inject registry

---

### 2.3 Make Rate Limiter Configurable

**Current Problem:** Global `limiter = Limiter(...)` singleton.

**Solution:** Create limiter in app factory, store in app.state.

```python
# src/reflex/api/rate_limiting.py

def create_limiter(settings: Settings) -> Limiter:
    """Create rate limiter from settings."""
    return Limiter(
        key_func=get_remote_address,
        default_limits=[f"{settings.rate_limit_requests}/{settings.rate_limit_window}second"],
    )

# Remove global limiter instance
```

**Files to modify:**
- `src/reflex/api/rate_limiting.py` - Add factory function
- `src/reflex/api/app.py` - Create limiter in `create_app()`
- `src/reflex/api/routes/events.py` - Get limiter from request.app.state

---

## Phase 3: Unify Filter API (Priority: HIGH)

### 3.1 Consolidate Filter Patterns

**Current Problem:** Two incompatible filter interfaces.

```python
# Pattern 1: Class-based (EventFilter)
class TypeFilter(EventFilter):
    def matches(self, event: Event) -> bool: ...

# Pattern 2: Function-based (Filter)
Filter = Callable[[Event, DecisionContext], bool]
```

**Solution:** Unify around class-based pattern with optional context.

```python
# src/reflex/agent/filters.py

from abc import ABC, abstractmethod
from typing import Protocol

class EventFilter(ABC):
    """Base class for event filters."""

    @abstractmethod
    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        """Check if event matches this filter.

        Args:
            event: The event to check
            context: Optional context with event history (for stateful filters)

        Returns:
            True if event matches filter criteria
        """
        ...

    def __and__(self, other: EventFilter) -> EventFilter:
        """Combine filters with AND logic."""
        return AndFilter([self, other])

    def __or__(self, other: EventFilter) -> EventFilter:
        """Combine filters with OR logic."""
        return OrFilter([self, other])

    def __invert__(self) -> EventFilter:
        """Negate filter."""
        return NotFilter(self)


@dataclass
class FilterContext:
    """Context for stateful filters."""
    events: list[Event] = field(default_factory=list)
    last_action_time: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# Concrete implementations
class TypeFilter(EventFilter):
    """Filter by event type."""

    def __init__(self, *types: str) -> None:
        self.types = set(types)

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        return event.type in self.types


class SourceFilter(EventFilter):
    """Filter by event source pattern."""

    def __init__(self, pattern: str) -> None:
        self.pattern = re.compile(pattern)

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        return bool(self.pattern.match(event.source))


class KeywordFilter(EventFilter):
    """Filter by keyword in event content."""

    def __init__(self, *keywords: str, case_sensitive: bool = False) -> None:
        self.keywords = keywords
        self.case_sensitive = case_sensitive

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        content = event.model_dump_json()
        if not self.case_sensitive:
            content = content.lower()
            return any(kw.lower() in content for kw in self.keywords)
        return any(kw in content for kw in self.keywords)


class RateLimitFilter(EventFilter):
    """Filter that rate-limits matching events."""

    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        if context is None:
            return True

        window_start = datetime.now(UTC) - timedelta(seconds=self.window_seconds)
        recent = [e for e in context.events if e.timestamp >= window_start]
        return len(recent) < self.max_events


# Convenience factory functions
def by_type(*types: str) -> TypeFilter:
    """Create a type filter."""
    return TypeFilter(*types)

def by_source(pattern: str) -> SourceFilter:
    """Create a source filter."""
    return SourceFilter(pattern)

def by_keyword(*keywords: str, case_sensitive: bool = False) -> KeywordFilter:
    """Create a keyword filter."""
    return KeywordFilter(*keywords, case_sensitive=case_sensitive)
```

**Files to modify:**
- `src/reflex/agent/filters.py` - Rewrite with unified API
- `src/reflex/agent/triggers.py` - Update to use new filter interface
- `src/reflex/core/context.py` - Remove `DecisionContext`, use `FilterContext`
- `tests/test_filters.py` - Update tests for new API

---

## Phase 4: Make Event Types Extensible (Priority: HIGH)

### 4.1 Event Type Registry

**Current Problem:** Adding event types requires modifying core `Event` union.

**Solution:** Runtime event type registry with validation.

```python
# src/reflex/core/events.py

from typing import ClassVar

class EventRegistry:
    """Registry for event types."""

    _types: ClassVar[dict[str, type[BaseEvent]]] = {}

    @classmethod
    def register(cls, event_class: type[BaseEvent]) -> type[BaseEvent]:
        """Register an event type. Can be used as decorator."""
        # Get the type discriminator value
        type_field = event_class.model_fields.get("type")
        if type_field is None or type_field.default is None:
            raise ValueError(f"Event class {event_class} must have a 'type' field with default")

        type_value = type_field.default
        if type_value in cls._types:
            raise ValueError(f"Event type '{type_value}' already registered")

        cls._types[type_value] = event_class
        return event_class

    @classmethod
    def get(cls, type_value: str) -> type[BaseEvent] | None:
        """Get event class by type value."""
        return cls._types.get(type_value)

    @classmethod
    def all_types(cls) -> list[type[BaseEvent]]:
        """Get all registered event types."""
        return list(cls._types.values())

    @classmethod
    def parse(cls, data: dict[str, Any]) -> BaseEvent:
        """Parse event data into appropriate event type."""
        event_type = data.get("type")
        if event_type is None:
            raise ValueError("Event data must have 'type' field")

        event_class = cls._types.get(event_type)
        if event_class is None:
            raise ValueError(f"Unknown event type: {event_type}")

        return event_class.model_validate(data)


# Register built-in types
@EventRegistry.register
class WebSocketEvent(BaseEvent):
    type: Literal["ws.message"] = "ws.message"
    connection_id: str
    content: str


@EventRegistry.register
class HTTPEvent(BaseEvent):
    type: Literal["http.request"] = "http.request"
    method: str
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | None = None


# ... other built-in types


# Dynamic Event union (regenerated when types are registered)
def get_event_union() -> type:
    """Get the current Event union type."""
    types = EventRegistry.all_types()
    if not types:
        return BaseEvent
    return Annotated[Union[tuple(types)], Field(discriminator="type")]


# For static type checking, keep the explicit union
Event = Annotated[
    WebSocketEvent | HTTPEvent | TimerEvent | LifecycleEvent,
    Field(discriminator="type"),
]
```

**User extension example:**
```python
# In user code
from reflex.core.events import BaseEvent, EventRegistry

@EventRegistry.register
class MyCustomEvent(BaseEvent):
    type: Literal["my.custom"] = "my.custom"
    custom_field: str
```

**Files to modify:**
- `src/reflex/core/events.py` - Add registry
- `src/reflex/infra/store.py` - Use registry for parsing
- Documentation - Add extension guide

---

## Phase 5: Split ReflexDeps (Priority: MEDIUM)

### 5.1 Separate Dependency Contexts

**Current Problem:** `ReflexDeps` is a grab-bag mixing concerns.

**Solution:** Split into focused dependency containers.

```python
# src/reflex/core/deps.py

from dataclasses import dataclass
from typing import Protocol

class EventPublisher(Protocol):
    """Protocol for event publishing."""
    async def __call__(self, event: Any) -> None: ...


@dataclass(frozen=True)
class StorageContext:
    """Storage-related dependencies."""
    store: EventStore
    db: AsyncSession


@dataclass(frozen=True)
class NetworkContext:
    """Network-related dependencies."""
    http: httpx.AsyncClient


@dataclass(frozen=True)
class ExecutionContext:
    """Execution metadata."""
    scope: str
    trace_id: str
    correlation_id: str | None = None


@dataclass(frozen=True)
class AgentDeps:
    """Complete dependencies for agent execution.

    Composed from smaller contexts for flexibility.
    """
    storage: StorageContext
    network: NetworkContext
    execution: ExecutionContext

    # Convenience properties for backward compatibility
    @property
    def store(self) -> EventStore:
        return self.storage.store

    @property
    def db(self) -> AsyncSession:
        return self.storage.db

    @property
    def http(self) -> httpx.AsyncClient:
        return self.network.http

    @property
    def scope(self) -> str:
        return self.execution.scope
```

**Files to modify:**
- `src/reflex/core/deps.py` - Split dependencies
- `src/reflex/agent/agents.py` - Update to use new structure
- `src/reflex/api/deps.py` - Update dependency providers

---

## Phase 6: Improve Error Handling (Priority: MEDIUM)

### 6.1 Create Error Classification System

```python
# src/reflex/core/errors.py

from enum import Enum

class ErrorCode(str, Enum):
    """Error codes for API responses."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    EVENT_NOT_FOUND = "EVENT_NOT_FOUND"
    PUBLICATION_FAILED = "PUBLICATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    STORE_ERROR = "STORE_ERROR"
    AGENT_ERROR = "AGENT_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ReflexError(Exception):
    """Base exception for Reflex errors."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    status_code: int = 500

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_response(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
            }
        }


class ValidationError(ReflexError):
    """Invalid input data."""
    code = ErrorCode.VALIDATION_ERROR
    status_code = 422


class EventNotFoundError(ReflexError):
    """Event not found."""
    code = ErrorCode.EVENT_NOT_FOUND
    status_code = 404


class PublicationError(ReflexError):
    """Failed to publish event."""
    code = ErrorCode.PUBLICATION_FAILED
    status_code = 500


class RateLimitError(ReflexError):
    """Rate limit exceeded."""
    code = ErrorCode.RATE_LIMITED
    status_code = 429


class StoreError(ReflexError):
    """Event store operation failed."""
    code = ErrorCode.STORE_ERROR
    status_code = 500


class AgentError(ReflexError):
    """Agent execution failed."""
    code = ErrorCode.AGENT_ERROR
    status_code = 500
```

### 6.2 Add Global Exception Handler

```python
# src/reflex/api/errors.py

from fastapi import Request
from fastapi.responses import JSONResponse

async def reflex_exception_handler(request: Request, exc: ReflexError) -> JSONResponse:
    """Handle ReflexError exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response(),
    )

# In app.py
app.add_exception_handler(ReflexError, reflex_exception_handler)
```

**Files to create:**
- `src/reflex/core/errors.py` - Error classes
- `src/reflex/api/errors.py` - Exception handlers

**Files to modify:**
- `src/reflex/api/app.py` - Register exception handler
- All route handlers - Use specific exceptions

---

## Phase 7: Fix Circular Imports (Priority: MEDIUM)

### 7.1 Restructure Module Dependencies

**Current Problem:** Multiple `if TYPE_CHECKING` imports and runtime imports inside functions.

**Solution:** Restructure modules to have clear dependency direction.

```
Current (circular):
core/events.py <-> infra/store.py
core/deps.py <-> infra/store.py

Target (acyclic):
core/events.py (no dependencies on infra)
core/types.py (shared type definitions)
    |
    v
infra/store.py (depends on core)
    |
    v
api/* (depends on core and infra)
```

**Strategy:**
1. Create `src/reflex/core/types.py` for shared type protocols
2. Move `Event` type definition to be self-contained
3. Use protocols instead of concrete types for cross-layer dependencies

```python
# src/reflex/core/types.py

from typing import Protocol, Any
from datetime import datetime

class EventProtocol(Protocol):
    """Protocol for events (avoids circular imports)."""
    id: str
    type: str
    source: str
    timestamp: datetime

    def model_dump_json(self) -> str: ...


class EventStoreProtocol(Protocol):
    """Protocol for event store operations."""

    async def publish(self, event: EventProtocol) -> None: ...
    async def ack(self, token: str) -> None: ...
    async def nack(self, token: str, error: str | None = None) -> None: ...
```

**Files to modify:**
- Create `src/reflex/core/types.py`
- Update `src/reflex/infra/store.py` to use protocols
- Remove runtime imports inside functions

---

## Phase 8: Enhance Health Checks (Priority: LOW)

### 8.1 Add Comprehensive Health Indicators

```python
# src/reflex/api/routes/health.py

@dataclass
class HealthIndicator:
    name: str
    status: Literal["healthy", "degraded", "unhealthy"]
    message: str | None = None
    latency_ms: float | None = None


async def check_database(app: FastAPI) -> HealthIndicator:
    """Check database connectivity."""
    start = time.monotonic()
    try:
        async with app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
        latency = (time.monotonic() - start) * 1000
        return HealthIndicator("database", "healthy", latency_ms=latency)
    except Exception as e:
        return HealthIndicator("database", "unhealthy", str(e))


async def check_event_queue(app: FastAPI) -> HealthIndicator:
    """Check event queue depth."""
    try:
        async with app.state.session_factory() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM events WHERE status = 'pending'")
            )
            pending = result.scalar()

        if pending > 10000:
            return HealthIndicator("event_queue", "degraded", f"{pending} pending events")
        return HealthIndicator("event_queue", "healthy", f"{pending} pending")
    except Exception as e:
        return HealthIndicator("event_queue", "unhealthy", str(e))


async def check_dlq(app: FastAPI) -> HealthIndicator:
    """Check dead-letter queue."""
    try:
        async with app.state.session_factory() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM events WHERE status = 'dlq'")
            )
            dlq_count = result.scalar()

        if dlq_count > 100:
            return HealthIndicator("dlq", "degraded", f"{dlq_count} events in DLQ")
        return HealthIndicator("dlq", "healthy", f"{dlq_count} in DLQ")
    except Exception as e:
        return HealthIndicator("dlq", "unhealthy", str(e))


@router.get("/health/detailed")
async def detailed_health(request: Request) -> dict[str, Any]:
    """Detailed health check with all indicators."""
    app = request.app
    indicators = await asyncio.gather(
        check_database(app),
        check_event_queue(app),
        check_dlq(app),
    )

    overall = "healthy"
    for ind in indicators:
        if ind.status == "unhealthy":
            overall = "unhealthy"
            break
        if ind.status == "degraded":
            overall = "degraded"

    return {
        "status": overall,
        "indicators": [asdict(ind) for ind in indicators],
    }
```

**Files to modify:**
- `src/reflex/api/routes/health.py` - Add detailed health endpoint

---

## Phase 9: Documentation & DX (Priority: LOW)

### 9.1 Add Extension Guide

Create `docs/extending.md`:
- How to add custom event types
- How to create custom agents
- How to implement custom filters
- How to deploy to distributed systems

### 9.2 Add End-to-End Example

Create `examples/basic/`:
- `main.py` - Complete working example
- `README.md` - Step-by-step guide

### 9.3 Define Public API

Update all `__init__.py` files with explicit `__all__`:

```python
# src/reflex/__init__.py

__all__ = [
    # Core
    "Event",
    "BaseEvent",
    "WebSocketEvent",
    "HTTPEvent",
    "TimerEvent",
    "LifecycleEvent",
    "EventRegistry",

    # Filters
    "EventFilter",
    "TypeFilter",
    "SourceFilter",
    "by_type",
    "by_source",

    # Agents
    "alert_agent",
    "summary_agent",
    "AlertResponse",
    "SummaryResponse",

    # Store
    "EventStore",

    # Config
    "Settings",
    "get_settings",
]
```

---

## Implementation Order

| Phase | Priority | Estimated Effort | Dependencies |
|-------|----------|------------------|--------------|
| 1.1 SQL Injection | CRITICAL | 2 hours | None |
| 1.2 Distributed Locks | CRITICAL | 4 hours | None |
| 2.1 Injectable Settings | HIGH | 2 hours | None |
| 2.2 Injectable Registry | HIGH | 2 hours | 2.1 |
| 2.3 Injectable Rate Limiter | HIGH | 1 hour | 2.1 |
| 3.1 Unified Filters | HIGH | 4 hours | None |
| 4.1 Event Registry | HIGH | 3 hours | None |
| 5.1 Split Deps | MEDIUM | 2 hours | None |
| 6.1 Error Classes | MEDIUM | 2 hours | None |
| 6.2 Exception Handler | MEDIUM | 1 hour | 6.1 |
| 7.1 Fix Circular Imports | MEDIUM | 3 hours | 4.1, 5.1 |
| 8.1 Health Checks | LOW | 2 hours | None |
| 9.1-9.3 Documentation | LOW | 4 hours | All above |

**Total estimated effort: ~32 hours**

---

## Success Criteria

1. **Security**: No SQL injection vulnerabilities (verified by security scan)
2. **Testability**: All components testable in isolation without global state
3. **Scalability**: Distributed locks work across multiple processes
4. **Consistency**: Single filter API pattern throughout codebase
5. **Extensibility**: Custom events can be added without modifying core
6. **Clarity**: No circular imports, clear module boundaries
7. **DX**: Comprehensive error messages, documented extension points

---

## Breaking Changes

This refactoring will introduce breaking changes:

1. **Filter API**: `Filter` callable type removed, use `EventFilter` class
2. **Dependencies**: `ReflexDeps` fields restructured (backward-compat properties added)
3. **Global imports**: `from reflex.config import settings` → `from reflex.config import get_settings`
4. **Trigger registration**: `register_trigger()` function removed, pass registry to loop

Migration guide will be provided in `docs/migration-v2.md`.
