# Reflex Testing Skill

Apply this knowledge when writing tests, debugging test failures, or setting up test fixtures.

## Test Organization

```
tests/
├── conftest.py          # Shared fixtures
├── test_events.py       # Event parsing/validation
├── test_filters.py      # Filter logic
├── test_triggers.py     # Trigger matching
├── test_agents.py       # Agent execution
├── test_store.py        # EventStore (integration)
├── test_api.py          # API endpoints
└── test_*.py            # Other tests
```

## Running Tests

```bash
# All tests in Docker (includes DB)
make test

# All tests locally
pytest tests/

# Specific file
pytest tests/test_events.py -v

# Specific test
pytest tests/test_events.py::test_event_registry -v

# With coverage
make test-cov

# Unit tests only (no DB)
pytest tests/ -m "not asyncio"
```

## Fixtures

### Mock Fixtures (Unit Tests)

```python
# In conftest.py
@pytest.fixture
def mock_store():
    """AsyncMock EventStore."""
    store = AsyncMock()
    store.publish = AsyncMock(return_value="event-id")
    store.ack = AsyncMock()
    store.nack = AsyncMock()
    return store

@pytest.fixture
def mock_deps(mock_store):
    """ReflexDeps with all mocked dependencies."""
    return ReflexDeps(
        store=mock_store,
        http=AsyncMock(),
        db=AsyncMock(),
        scope="test-scope",
    )
```

### Using Mock Fixtures

```python
def test_something(mock_store, mock_deps):
    # mock_store and mock_deps are ready to use
    assert mock_store.publish.called
```

### Real Fixtures (Integration Tests)

```python
@pytest.fixture
async def store(database_url):
    """Real EventStore connected to test DB."""
    async with EventStore(database_url) as store:
        yield store

@pytest.fixture
async def real_deps(store):
    """ReflexDeps with real dependencies."""
    async with httpx.AsyncClient() as http:
        yield ReflexDeps(store=store, http=http, ...)
```

### Using Real Fixtures

```python
@pytest.mark.asyncio
async def test_store_publish(store):
    event = WebSocketEvent(source="test", connection_id="c1", content="hi")
    event_id = await store.publish(event)
    assert event_id is not None
```

## Async Testing

pytest-asyncio is configured with `asyncio_mode = "auto"`:

```python
# No decorator needed for async tests
async def test_async_operation(store):
    result = await store.publish(event)
    assert result

# Or explicitly mark
@pytest.mark.asyncio
async def test_explicit_async():
    ...
```

## Testing Patterns

### Testing Events

```python
def test_event_creation():
    event = WebSocketEvent(
        source="test",
        connection_id="conn-1",
        content="hello",
    )
    assert event.type == "ws.message"
    assert event.id is not None

def test_event_registry():
    data = {"type": "ws.message", "source": "test", ...}
    event = EventRegistry.parse(data)
    assert isinstance(event, WebSocketEvent)
```

### Testing Filters

```python
def test_type_filter():
    filter = TypeFilter(types=["ws.message"])
    ws_event = WebSocketEvent(source="test", ...)
    http_event = HTTPEvent(source="test", ...)

    assert filter.matches(ws_event)
    assert not filter.matches(http_event)

def test_filter_composition():
    filter = TypeFilter(types=["ws.message"]) & SourceFilter(pattern=r"ws:vip-.*")
    ...
```

### Testing Agents

```python
@pytest.mark.asyncio
async def test_agent_execution(mock_deps):
    agent = MyAgent()
    ctx = AgentContext(
        event=WebSocketEvent(source="test", ...),
        deps=mock_deps,
    )

    await agent.run(ctx)

    mock_deps.store.publish.assert_called_once()
```

### Testing API Endpoints

```python
from fastapi.testclient import TestClient

def test_health_endpoint(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

## Integration Tests

Require `DATABASE_URL` environment variable:

```bash
DATABASE_URL="postgresql+asyncpg://reflex:reflex@localhost:5432/reflex_test" \
pytest tests/test_store.py -v
```

Or run in Docker (handles DB automatically):
```bash
make test
```

## Debugging Tests

```bash
# Stop on first failure
pytest -x

# Show print output
pytest -s

# Verbose
pytest -v

# Run last failed
pytest --lf

# Drop into debugger on failure
pytest --pdb
```

## Key Files

- `tests/conftest.py` - All fixtures
- `pyproject.toml` - pytest configuration
- `.github/workflows/ci.yml` - CI test setup
