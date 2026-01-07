# Reflex

Real-time AI Agent Template Project

## Quick Start

```bash
# Clone and setup
git clone https://github.com/yourorg/reflex my-agent
cd my-agent
cp .env.example .env

# Start everything
docker compose up
```

Your agent is running at:
- **API**: http://localhost:8000
- **WebSocket**: ws://localhost:8000/ws
- **Health**: http://localhost:8000/health

Now rip out the example agent and build your own.

## What is Reflex?

Reflex is a production-ready template for building real-time AI agents as continuous control systems. Unlike request/response chatbots, Reflex agents:

- **React to events** from multiple sources (WebSocket, HTTP, timers)
- **Maintain state** across interactions with persistent event storage
- **Observe everything** with built-in tracing via Logfire
- **Scale horizontally** with concurrent consumer support

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI Server                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │WebSocket │  │   HTTP   │  │  Health  │  │   Agent Loop     │ │
│  │ Handler  │  │ Endpoints│  │  Checks  │  │   (Background)   │ │
│  └────┬─────┘  └────┬─────┘  └──────────┘  └────────┬─────────┘ │
└───────┼─────────────┼───────────────────────────────┼───────────┘
        │             │                               │
        v             v                               v
┌─────────────────────────────────────────────────────────────────┐
│                        EventStore                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   publish() │  │ subscribe() │  │  ack() / nack()         │  │
│  │             │  │  (LISTEN/   │  │  (exponential backoff)  │  │
│  │             │  │   NOTIFY)   │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            v
┌─────────────────────────────────────────────────────────────────┐
│                       PostgreSQL                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  events table (id, type, payload, status, attempts...)  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Event Flow

1. **Ingestion**: Events arrive via WebSocket or HTTP
2. **Persistence**: EventStore persists to PostgreSQL and fires NOTIFY
3. **Processing**: Agent loop receives events via subscribe()
4. **Execution**: PydanticAI agent processes with tools
5. **Completion**: Events are ack'd (completed) or nack'd (retry with backoff)

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| EventStore | `src/reflex/infra/store.py` | Persistent event queue with pub/sub |
| Events | `src/reflex/core/events.py` | Pydantic models with discriminated unions |
| Agent | `src/reflex/agent/agents.py` | PydanticAI agent with tools |
| API | `src/reflex/api/app.py` | FastAPI with WebSocket support |
| Config | `src/reflex/config.py` | Pydantic-settings configuration |

## Project Structure

```
reflex/
├── docker/              # Docker configuration
│   └── Dockerfile       # Multi-stage production build
├── src/reflex/          # Source code
│   ├── infra/           # Infrastructure (keep this)
│   │   ├── database.py  # PostgreSQL connection setup
│   │   └── store.py     # EventStore implementation
│   ├── core/            # Core types (modify this)
│   │   └── events.py    # Event definitions
│   ├── agent/           # Agent logic (replace this)
│   │   └── agents.py    # PydanticAI agent and tools
│   └── api/             # API layer (modify this)
│       └── app.py       # FastAPI application
├── tests/               # Test suite
│   ├── conftest.py      # Pytest fixtures
│   ├── test_config.py   # Configuration tests
│   └── test_store.py    # EventStore integration tests
├── scripts/             # Utility scripts
│   ├── replay.py        # Event replay tool
│   └── dlq.py           # Dead-letter queue management
└── .github/workflows/   # CI/CD
    └── ci.yml           # Test and lint pipeline
```

## Development

```bash
# Start development environment with hot reload
make dev

# Run all tests
make test

# Run only unit tests (no database required)
make test-unit

# Lint and type check
make lint
make type-check

# Format code
make format
```

### Testing

Tests are organized into unit and integration tests:

```bash
# Unit tests run without external dependencies
pytest tests/ -m "not asyncio"

# Integration tests require DATABASE_URL
DATABASE_URL="postgresql://..." pytest tests/test_store.py
```

## Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection (e.g., `postgresql://user:pass@localhost/reflex`) |
| `OPENAI_API_KEY` | Yes | OpenAI API key for PydanticAI agent |
| `LOGFIRE_TOKEN` | No | Logfire API token for observability |
| `DB_POOL_MIN` | No | Minimum connection pool size (default: 5) |
| `DB_POOL_MAX` | No | Maximum connection pool size (default: 20) |
| `EVENT_MAX_ATTEMPTS` | No | Max retry attempts before DLQ (default: 3) |
| `EVENT_RETRY_BASE_DELAY` | No | Base delay in seconds for retry backoff (default: 1.0) |
| `EVENT_RETRY_MAX_DELAY` | No | Maximum delay in seconds for retry backoff (default: 60.0) |

## Extending Reflex

### Adding Event Types

Edit `src/reflex/core/events.py`:

```python
class MyCustomEvent(BaseEvent):
    """My custom event type."""
    type: Literal["my.custom"] = "my.custom"
    custom_field: str

# Add to the discriminated union
Event = Annotated[
    WebSocketEvent | HTTPEvent | TimerEvent | LifecycleEvent | MyCustomEvent,
    Field(discriminator="type"),
]
```

### Adding Agent Tools

Edit `src/reflex/agent/agents.py`:

```python
@agent.tool
async def my_tool(ctx: RunContext[AgentDeps], param: str) -> str:
    """Tool description for the LLM."""
    # Your tool implementation
    return result
```

### Adding API Endpoints

Edit `src/reflex/api/app.py`:

```python
@app.post("/my-endpoint")
async def my_endpoint(request: MyRequest, deps: Annotated[AppDeps, Depends(get_deps)]):
    event = MyCustomEvent(source="http:my-endpoint", custom_field=request.field)
    await deps.store.publish(event)
    return {"status": "accepted"}
```

## Scalability Considerations

### Current Architecture (PostgreSQL LISTEN/NOTIFY)

The current implementation uses PostgreSQL's LISTEN/NOTIFY for real-time event delivery. This is suitable for:

- **Single-region deployments**
- **Moderate throughput** (thousands of events/second)
- **Teams wanting minimal infrastructure**

### Scaling Beyond PostgreSQL

For higher scale requirements, the EventStore interface is designed to be swappable:

**Redis Streams** (Recommended for high throughput):
```python
# Future: Redis-backed EventStore
class RedisEventStore:
    """Drop-in replacement using Redis Streams."""
    async def publish(self, event): ...
    async def subscribe(self, event_types): ...
```

Benefits of Redis Streams:
- **Higher throughput**: 100k+ events/second
- **Consumer groups**: Built-in load balancing across consumers
- **Persistence**: Optional persistence with AOF/RDB
- **Pub/Sub**: Native support for fan-out patterns

**Migration Path**:
1. Implement `RedisEventStore` with same interface
2. Add `EVENT_BACKEND` config option (`postgres` | `redis`)
3. Swap implementation in dependency injection
4. PostgreSQL remains for event history/replay

### Horizontal Scaling

The current design supports multiple concurrent consumers:

```yaml
# docker-compose.yml - Scale consumers
services:
  agent:
    deploy:
      replicas: 3
```

Events are claimed with `FOR UPDATE SKIP LOCKED`, preventing duplicate processing.

## Dead-Letter Queue (DLQ)

Failed events (after max retries with exponential backoff) move to the DLQ:

```bash
# List DLQ events
python scripts/dlq.py list

# Retry a specific event
python scripts/dlq.py retry <event-id>

# Retry all DLQ events
python scripts/dlq.py retry-all
```

## Observability

Reflex is pre-configured for Logfire observability:

```python
# Traces are automatic for:
# - HTTP requests
# - WebSocket connections
# - Event store operations
# - Agent tool calls

# Add custom spans
with logfire.span("my-operation", key=value):
    ...
```

## Documentation

See the `.github/plans/` directory for detailed documentation:

- `prd.md` - Product Requirements Document
- `developer_brief.md` - Development Plan

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

MIT License - see LICENSE file for details.
