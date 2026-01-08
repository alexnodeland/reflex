# Getting Started

Get Reflex running in minutes.

## Prerequisites

- Docker and Docker Compose
- OpenAI API key (for AI agents)
- Optional: Logfire token (for observability)

## Quick Start

=== "Docker (Recommended)"

    ```bash
    # Clone and setup
    git clone https://github.com/alexnodeland/reflex my-agent
    cd my-agent
    cp .env.example .env

    # Add your OpenAI key to .env
    echo "OPENAI_API_KEY=sk-..." >> .env

    # Start everything
    docker compose up
    ```

=== "Local Development"

    ```bash
    # Clone and setup
    git clone https://github.com/alexnodeland/reflex my-agent
    cd my-agent
    cp .env.example .env

    # Install dependencies
    pip install uv
    uv pip install -e ".[dev]"

    # Start PostgreSQL (required)
    docker compose up db -d

    # Run the app
    uv run uvicorn reflex.api.app:app --reload
    ```

## Verify Installation

Once running, your agent is available at:

| Endpoint | URL | Description |
|----------|-----|-------------|
| API | `http://localhost:8000` | REST API |
| WebSocket | `ws://localhost:8000/ws` | Real-time events |
| Health | `http://localhost:8000/health` | Basic health check |
| Detailed Health | `http://localhost:8000/health/detailed` | Component status |

Test the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "healthy"}
```

## What's Running

When you start Reflex, you get:

1. **FastAPI Server** - Handles HTTP and WebSocket connections
2. **PostgreSQL** - Stores events and provides pub/sub via LISTEN/NOTIFY
3. **Agent Loop** - Background task that processes events

## Send Your First Event

=== "WebSocket"

    ```python
    import asyncio
    import websockets
    import json

    async def send_event():
        async with websockets.connect("ws://localhost:8000/ws") as ws:
            event = {"type": "websocket", "source": "test", "content": "Hello!"}
            await ws.send(json.dumps(event))
            response = await ws.recv()
            print(response)

    asyncio.run(send_event())
    ```

=== "HTTP"

    ```bash
    curl -X POST http://localhost:8000/events \
      -H "Content-Type: application/json" \
      -d '{"type": "http", "source": "test", "content": "Hello!"}'
    ```

## Next Steps

1. Explore the [example agent](https://github.com/alexnodeland/reflex/tree/main/examples/basic)
2. Understand the [architecture](architecture.md)
3. Learn how to [extend Reflex](extending.md) with your own events and agents
4. Review [configuration options](configuration.md)
