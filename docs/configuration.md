# Configuration

Reflex is configured via environment variables. Copy `.env.example` to `.env` to get started.

## Required Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | OpenAI API key for PydanticAI agent |

!!! example "Database URL Format"
    ```
    postgresql://user:password@localhost:5432/reflex
    ```

## Optional Variables

### Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `LOGFIRE_TOKEN` | — | Logfire API token for tracing |

### Database Pool

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_POOL_MIN` | `5` | Minimum connection pool size |
| `DB_POOL_MAX` | `20` | Maximum connection pool size |

### Event Processing

| Variable | Default | Description |
|----------|---------|-------------|
| `EVENT_MAX_ATTEMPTS` | `3` | Max retry attempts before DLQ |
| `EVENT_RETRY_BASE_DELAY` | `1.0` | Base delay (seconds) for exponential backoff |
| `EVENT_RETRY_MAX_DELAY` | `60.0` | Maximum delay (seconds) for retry backoff |

## Example Configuration

=== "Development"

    ```bash title=".env"
    DATABASE_URL=postgresql://reflex:reflex@localhost:5432/reflex
    OPENAI_API_KEY=sk-...

    # Lower retry delays for faster iteration
    EVENT_MAX_ATTEMPTS=2
    EVENT_RETRY_BASE_DELAY=0.5
    ```

=== "Production"

    ```bash title=".env"
    DATABASE_URL=postgresql://reflex:${DB_PASSWORD}@db.example.com:5432/reflex
    OPENAI_API_KEY=sk-...
    LOGFIRE_TOKEN=...

    # Higher pool size for load
    DB_POOL_MIN=10
    DB_POOL_MAX=50

    # More retries with longer backoff
    EVENT_MAX_ATTEMPTS=5
    EVENT_RETRY_BASE_DELAY=2.0
    EVENT_RETRY_MAX_DELAY=300.0

    # Enable distributed locking
    LOCK_BACKEND=postgres
    ```

## Distributed Deployments

For production deployments with multiple instances:

!!! warning "Required for Multiple Instances"
    Enable PostgreSQL-based locking to prevent duplicate event processing.

```bash
# Enable distributed locking
LOCK_BACKEND=postgres

# Configure pool size based on instance count
# Total connections = instances × DB_POOL_MAX
DATABASE_POOL_SIZE=5
DATABASE_POOL_MAX_OVERFLOW=10
```
