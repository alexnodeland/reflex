---
description: Run tests with smart defaults
argument-hint: "[path] [options]"
---

# Run Tests

Run tests for: **$ARGUMENTS**

## Quick Commands

```bash
# Run all tests in Docker (includes DB)
make test

# Run all tests locally (needs DATABASE_URL for integration tests)
pytest tests/

# Run specific test file
pytest tests/test_events.py -v

# Run specific test
pytest tests/test_events.py::test_event_registry -v

# Run with coverage
make test-cov
```

## Test Types

### Unit Tests (no DB required)
```bash
pytest tests/ -m "not asyncio" -v
```

These test:
- Event parsing and validation
- Filter logic
- Trigger matching
- Pure functions

### Integration Tests (requires DATABASE_URL)
```bash
DATABASE_URL="postgresql+asyncpg://reflex:reflex@localhost:5432/reflex_test" \
pytest tests/test_store.py -v
```

These test:
- EventStore operations
- Database interactions
- Full event flow

## Test Fixtures

### For Unit Tests
```python
def test_something(mock_store, mock_deps):
    # mock_store - AsyncMock with publish/subscribe/ack/nack
    # mock_deps - ReflexDeps with all mocked dependencies
```

### For Integration Tests
```python
@pytest.mark.asyncio
async def test_something(store, real_deps):
    # store - Real EventStore connected to test DB
    # real_deps - ReflexDeps with real dependencies
```

## Debugging Tests

```bash
# Stop on first failure
pytest tests/ -x

# Show print statements
pytest tests/ -s

# Verbose output
pytest tests/ -v

# Run last failed
pytest tests/ --lf
```

If a test path is provided, run that specific test. Otherwise, run `make test`.
