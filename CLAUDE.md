# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
# Development
make dev                  # Start with docker compose (includes PostgreSQL)
make dev-build            # Rebuild and start

# Testing
make test                 # Run all tests in Docker
pytest tests/             # Run all tests locally
pytest tests/test_file.py::test_name  # Run single test
pytest tests/ -m "not asyncio"        # Unit tests only (no DB required)
DATABASE_URL="..." pytest tests/test_store.py  # Integration tests

# Code Quality
make lint                 # ruff check src tests
make lint-fix             # Auto-fix lint issues
make format               # ruff format src tests
make type-check           # pyright src
make ci                   # Run full CI pipeline locally

# Database
make db-shell             # psql into PostgreSQL
make migrate              # Run migrations
```

## Architecture

Reflex is an event-driven AI agent framework using PostgreSQL LISTEN/NOTIFY for real-time pub/sub.

### Event Flow
1. Events arrive via WebSocket (`/ws`) or HTTP (`/events`)
2. `EventStore.publish()` persists to PostgreSQL and fires NOTIFY
3. Agent loop receives events via `EventStore.subscribe()` (uses `FOR UPDATE SKIP LOCKED`)
4. Triggers match events to agents via composable filters
5. Events are `ack()`'d on success or `nack()`'d for retry with exponential backoff

### Key Abstractions

**Events** (`src/reflex/core/events.py`):
- Use `@EventRegistry.register` decorator for custom events
- Must have `type: Literal["my.type"] = "my.type"` field
- Built-in: `WebSocketEvent`, `HTTPEvent`, `TimerEvent`, `LifecycleEvent`

**Filters** (`src/reflex/agent/filters.py`):
- Compose with `&` (and), `|` (or), `~` (not) operators
- Factory functions: `type_filter()`, `source_filter()`, `keyword_filter()`
- Stateful: `RateLimitFilter`, `DedupeFilter`

**Triggers** (`src/reflex/agent/triggers.py`):
- Connect filters to agents: `Trigger(name, filter, agent, scope_key)`
- Use `@trigger` decorator on agent classes
- `TriggerRegistry` manages trigger lookup

**Dependencies** (`src/reflex/core/deps.py`):
- `ReflexDeps`: Main container passed to PydanticAI tools via `RunContext[ReflexDeps]`
- Contains: `store` (EventStore), `http` (AsyncClient), `db` (AsyncSession), `scope`

### Module Organization

- `src/reflex/infra/` - Infrastructure (EventStore, database, observability) - keep stable
- `src/reflex/core/` - Core types (events, deps, errors) - extend carefully
- `src/reflex/agent/` - Agent logic (triggers, filters, agents) - primary extension point
- `src/reflex/api/` - FastAPI routes and middleware

### Testing Patterns

Unit tests use mock fixtures from `tests/conftest.py`:
```python
def test_something(mock_store, mock_deps):
    # mock_store is AsyncMock with publish/subscribe/ack/nack
    # mock_deps is ReflexDeps with all mocked dependencies
```

Integration tests require `DATABASE_URL` and use real fixtures (`store`, `real_deps`).

## Code Style

- Python 3.11+, strict pyright type checking
- ruff for linting (includes async, security, bugbear rules)
- Line length: 100 characters
- Use `from __future__ import annotations` for forward references
- Place runtime-only imports in `if TYPE_CHECKING:` blocks to avoid circular imports
