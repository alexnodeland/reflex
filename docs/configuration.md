# Configuration

Reflex is configured via environment variables. Copy `.env.example` to `.env` to get started.

## Required Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (e.g., `postgresql://user:pass@localhost/reflex`) |
| `OPENAI_API_KEY` | OpenAI API key for PydanticAI agent |

## Optional Variables

### Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `LOGFIRE_TOKEN` | - | Logfire API token for observability |

### Database Pool

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_POOL_MIN` | 5 | Minimum connection pool size |
| `DB_POOL_MAX` | 20 | Maximum connection pool size |

### Event Processing

| Variable | Default | Description |
|----------|---------|-------------|
| `EVENT_MAX_ATTEMPTS` | 3 | Max retry attempts before moving to DLQ |
| `EVENT_RETRY_BASE_DELAY` | 1.0 | Base delay in seconds for exponential backoff |
| `EVENT_RETRY_MAX_DELAY` | 60.0 | Maximum delay in seconds for retry backoff |

## Example Configuration

```bash
# .env
DATABASE_URL=postgresql://reflex:reflex@localhost:5432/reflex
OPENAI_API_KEY=sk-...

# Optional
LOGFIRE_TOKEN=...
DB_POOL_MIN=5
DB_POOL_MAX=20
EVENT_MAX_ATTEMPTS=5
EVENT_RETRY_BASE_DELAY=2.0
EVENT_RETRY_MAX_DELAY=300.0
```

## Distributed Deployments

For production deployments with multiple instances:

```bash
# Enable PostgreSQL-based locking
LOCK_BACKEND=postgres

# Configure pool size based on instance count
DATABASE_POOL_SIZE=5
DATABASE_POOL_MAX_OVERFLOW=10
```
