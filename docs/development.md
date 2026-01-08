# Development

Commands and workflows for developing Reflex.

## Development Commands

```bash
# Start development environment with hot reload
make dev

# Rebuild and start
make dev-build

# Run interactive demo (server must be running)
make demo
```

## Testing

```bash
# Run all tests in Docker
make test

# Run all tests locally
pytest tests/

# Run a single test
pytest tests/test_file.py::test_name

# Unit tests only (no database required)
pytest tests/ -m "not asyncio"

# Integration tests (requires DATABASE_URL)
DATABASE_URL="postgresql://..." pytest tests/test_store.py
```

### Test Organization

Tests are organized into unit and integration tests:

- **Unit tests**: Run without external dependencies, use mock fixtures
- **Integration tests**: Require `DATABASE_URL`, use real fixtures

Mock fixtures from `tests/conftest.py`:

```python
def test_something(mock_store, mock_deps):
    # mock_store is AsyncMock with publish/subscribe/ack/nack
    # mock_deps is ReflexDeps with all mocked dependencies
```

## Code Quality

```bash
# Lint (ruff check)
make lint

# Auto-fix lint issues
make lint-fix

# Format code
make format

# Type check (pyright)
make type-check

# Run full CI pipeline locally
make ci
```

## Database

```bash
# Open psql shell
make db-shell

# Run migrations
make migrate
```

## Code Style

- Python 3.11+, strict pyright type checking
- ruff for linting (includes async, security, bugbear rules)
- Line length: 100 characters
- Use `from __future__ import annotations` for forward references
- Place runtime-only imports in `if TYPE_CHECKING:` blocks
