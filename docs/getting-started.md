# Getting Started

Get Reflex running in minutes.

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

| Endpoint | URL |
|----------|-----|
| API | http://localhost:8000 |
| WebSocket | ws://localhost:8000/ws |
| Health | http://localhost:8000/health |
| Detailed Health | http://localhost:8000/health/detailed |

## What's Running

When you start Reflex, you get:

1. **FastAPI Server** - Handles HTTP and WebSocket connections
2. **PostgreSQL** - Stores events and provides pub/sub via LISTEN/NOTIFY
3. **Agent Loop** - Background task that processes events

## Next Steps

1. Explore the [example agent](../examples/basic/)
2. Understand the [architecture](architecture.md)
3. Learn how to [extend Reflex](extending.md) with your own events and agents

## Requirements

- Docker and Docker Compose
- OpenAI API key (for AI agents)
- Optional: Logfire token (for observability)

See [Configuration](configuration.md) for all environment variables.
