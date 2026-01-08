# Reflex Documentation

Welcome to the Reflex documentation. Reflex is a production-ready template for building real-time AI agents as continuous control systems.

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](getting-started.md) | Quick start guide and setup instructions |
| [Architecture](architecture.md) | System design, event flow, and key components |
| [Configuration](configuration.md) | Environment variables and settings |
| [Development](development.md) | Development commands, testing, and code quality |
| [Extending](extending.md) | Custom events, agents, filters, and triggers |
| [Scaling](scaling.md) | Horizontal scaling and backend options |
| [Operations](operations.md) | DLQ management and observability |

## Key Features

- **React to events** from multiple sources (WebSocket, HTTP, timers)
- **Maintain state** across interactions with persistent event storage
- **Observe everything** with built-in tracing via Logfire
- **Scale horizontally** with concurrent consumer support

## Project Structure

```
reflex/
├── src/reflex/
│   ├── infra/     # Infrastructure (EventStore, database) - keep stable
│   ├── core/      # Core types (events, deps, errors) - extend carefully
│   ├── agent/     # Agent logic (triggers, filters) - primary extension point
│   └── api/       # FastAPI routes and middleware
├── tests/         # Test suite
├── scripts/       # Utility scripts (replay, DLQ management)
├── examples/      # Working examples
└── docs/          # Documentation (you are here)
```

## Quick Links

- [Examples](../examples/basic/) - Working example with custom events and triggers
- [Contributing](../CONTRIBUTING.md) - Development guidelines
- [License](../LICENSE) - MIT License
