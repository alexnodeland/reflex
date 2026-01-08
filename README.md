# Reflex

[![CI](https://github.com/alexnodeland/reflex/actions/workflows/ci.yml/badge.svg)](https://github.com/alexnodeland/reflex/actions/workflows/ci.yml)
[![Docs](https://github.com/alexnodeland/reflex/actions/workflows/docs.yml/badge.svg)](https://alexnodeland.github.io/reflex)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Real-time AI Agent Template Project

## Quick Start

```bash
# Clone and setup
git clone https://github.com/alexnodeland/reflex my-agent
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

📖 **[View the full documentation](https://alexnodeland.github.io/reflex)**

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Setup and first steps |
| [Architecture](docs/architecture.md) | System design and event flow |
| [Extending](docs/extending.md) | Custom events, agents, and filters |
| [Configuration](docs/configuration.md) | Environment variables |
| [Development](docs/development.md) | Commands and testing |
| [Scaling](docs/scaling.md) | Horizontal scaling |
| [Operations](docs/operations.md) | DLQ and observability |

## Development

```bash
make dev          # Start with hot reload
make test         # Run tests
make lint         # Check code
make docs         # Serve docs locally
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
