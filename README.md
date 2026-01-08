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

## What is Reflex?

Reflex is a production-ready template for building real-time AI agents as continuous control systems. Unlike request/response chatbots, Reflex agents:

- **React to events** from multiple sources (WebSocket, HTTP, timers)
- **Maintain state** across interactions with persistent event storage
- **Observe everything** with built-in tracing via Logfire
- **Scale horizontally** with concurrent consumer support

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | Setup and first steps |
| [Architecture](docs/architecture.md) | System design and event flow |
| [Configuration](docs/configuration.md) | Environment variables |
| [Development](docs/development.md) | Commands and testing |
| [Extending](docs/extending.md) | Custom events, agents, and filters |
| [Scaling](docs/scaling.md) | Horizontal scaling options |
| [Operations](docs/operations.md) | DLQ and observability |

## Development

```bash
make dev          # Start with hot reload
make test         # Run tests
make lint         # Check code
make format       # Format code
```

See [docs/development.md](docs/development.md) for full details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
