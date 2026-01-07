# Contributing to Reflex

Thank you for your interest in contributing to Reflex! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL 16+ (or use Docker)

### Quick Start

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourorg/reflex.git
   cd reflex
   ```

2. **Copy environment file:**

   ```bash
   cp .env.example .env
   ```

3. **Start development environment:**

   ```bash
   docker compose up
   ```

   Or without Docker:

   ```bash
   pip install uv
   uv pip install -e ".[dev]"
   ```

4. **Run migrations:**

   ```bash
   python scripts/migrate.py
   ```

## Development Workflow

### Code Style

We use `ruff` for linting and formatting, and `pyright` for type checking.

```bash
# Check for linting issues
ruff check src tests

# Auto-fix linting issues
ruff check --fix src tests

# Format code
ruff format src tests

# Type check
pyright src tests
```

### Running Tests

```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=reflex --cov-report=html

# Run specific test file
pytest tests/test_events.py -v

# Run integration tests (requires DATABASE_URL)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/test pytest tests/test_store.py -v
```

### Commit Guidelines

We follow conventional commit format:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

Examples:

```
feat: add WebSocket reconnection logic
fix: resolve race condition in event subscription
docs: update API documentation
```

### Pull Request Process

1. **Create a feature branch:**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code style guidelines.

3. **Write tests** for new functionality.

4. **Ensure all checks pass:**

   ```bash
   ruff check src tests
   ruff format --check src tests
   pyright src tests
   pytest -v
   ```

5. **Push and create a PR:**

   ```bash
   git push origin feature/your-feature-name
   ```

6. **Fill out the PR template** with a clear description.

## Project Structure

```
reflex/
├── src/reflex/
│   ├── config.py        # Configuration (pydantic-settings)
│   ├── infra/           # Infrastructure layer
│   │   ├── database.py  # Database connections
│   │   ├── store.py     # EventStore implementation
│   │   ├── locks.py     # Scoped locking
│   │   └── observability.py  # Logfire setup
│   ├── core/            # Core domain types
│   │   ├── events.py    # Event type definitions
│   │   ├── context.py   # DecisionContext
│   │   └── deps.py      # Dependency container
│   ├── agent/           # Agent layer
│   │   ├── filters.py   # Event filters
│   │   ├── triggers.py  # Trigger functions
│   │   ├── agents.py    # PydanticAI agents
│   │   └── loop.py      # Main processing loop
│   └── api/             # API layer
│       ├── app.py       # FastAPI application
│       ├── deps.py      # API dependencies
│       └── routes/      # Route handlers
├── tests/               # Test suite
├── scripts/             # Utility scripts
└── docker/              # Docker configuration
```

## Adding New Event Types

1. Define your event type in `src/reflex/core/events.py`:

   ```python
   class MyEvent(BaseEvent):
       type: Literal["my.event"] = "my.event"
       # Add your fields here
   ```

2. Add it to the `Event` union:

   ```python
   Event = Annotated[
       Union[WebSocketEvent, HTTPEvent, TimerEvent, LifecycleEvent, MyEvent],
       Field(discriminator="type")
   ]
   ```

3. Write tests in `tests/test_events.py`.

## Adding New Filters

1. Create your filter function in `src/reflex/agent/filters.py`:

   ```python
   def my_filter(pattern: str) -> Filter:
       def _filter(event: Event) -> bool:
           # Your filter logic
           return True
       return _filter
   ```

2. Write tests in `tests/test_filters.py`.

## Adding New Triggers

1. Create your trigger function in `src/reflex/agent/triggers.py`:

   ```python
   def my_trigger(threshold: int) -> Trigger:
       async def _trigger(ctx: DecisionContext, deps: ReflexDeps) -> Any | None:
           # Your trigger logic
           if condition_met:
               return {"triggered": True, "data": ...}
           return None
       return _trigger
   ```

2. Write tests in `tests/test_trigger_funcs.py`.

## Utility Scripts

### migrate.py

Create database tables:

```bash
python scripts/migrate.py
```

### replay.py

Replay historical events:

```bash
python scripts/replay.py --last 1h
python scripts/replay.py --start 2024-01-01T00:00:00 --type ws.message
```

### dlq.py

Manage dead-letter queue:

```bash
python scripts/dlq.py list
python scripts/dlq.py retry <event_id>
python scripts/dlq.py retry-all
```

## Questions?

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
- Join discussions in pull requests

Thank you for contributing!
