# Reflex

Real-time AI Agent Template Project

## Quick Start

```bash
git clone https://github.com/yourorg/reflex my-agent
cd my-agent
cp .env.example .env
docker compose up
```

Your agent is running. Now rip out the example and build your own.

## What is Reflex?

Reflex is a template project for building real-time AI agents as continuous control systems. It provides production-ready infrastructure:

- **Docker Compose** with hot reload
- **PostgreSQL** with async access and LISTEN/NOTIFY
- **Logfire** observability (pre-configured for full-stack tracing)
- **FastAPI** with WebSocket support and proper lifecycle management
- **Health checks** and graceful shutdown
- **CI/CD templates** (GitHub Actions)
- **Test setup** with pytest-asyncio

## Project Structure

```
reflex/
├── docker/              # Docker configuration
├── src/reflex/          # Source code
│   ├── infra/           # Infrastructure (keep this)
│   ├── core/            # Core types (modify this)
│   ├── agent/           # Agent logic (replace this)
│   └── api/             # API layer (modify this)
├── tests/               # Test suite
├── scripts/             # Utility scripts
└── .github/workflows/   # CI/CD
```

## Development

```bash
# Start development environment
make dev

# Run tests
make test

# Lint and type check
make lint
make type-check
```

## Configuration

Copy `.env.example` to `.env` and configure:

- `DATABASE_URL` - PostgreSQL connection string
- `OPENAI_API_KEY` - OpenAI API key for agent
- `LOGFIRE_TOKEN` - Logfire API token (optional)

## Documentation

See the `.github/plans/` directory for detailed documentation:

- `prd.md` - Product Requirements Document
- `developer_brief.md` - Development Plan

## License

MIT License - see LICENSE file for details.
