# Reflex Database Skill

Apply this knowledge when working with PostgreSQL, migrations, EventStore, or debugging database issues.

## Database Architecture

Reflex uses PostgreSQL with:
- **LISTEN/NOTIFY** for real-time event distribution
- **FOR UPDATE SKIP LOCKED** for concurrent consumer safety
- **AsyncPG** for async operations
- **SQLModel/SQLAlchemy** for ORM

## EventStore

The `EventStore` handles all event persistence and distribution.

### Publishing

```python
await store.publish(event)
# 1. Inserts event into DB
# 2. Fires NOTIFY on channel
# 3. Returns event ID
```

### Subscribing

```python
async for event in store.subscribe():
    # Uses FOR UPDATE SKIP LOCKED
    # Only one consumer gets each event
    try:
        await process(event)
        await store.ack(event.id)
    except Exception:
        await store.nack(event.id)
```

### Acknowledgment

```python
await store.ack(event_id)    # Mark as processed, remove from queue
await store.nack(event_id)   # Mark for retry with backoff
```

## Connection Configuration

```python
# From settings
DATABASE_URL = "postgresql+asyncpg://user:pass@host:5432/db"

# Connection pool settings
POOL_SIZE = 10
MAX_OVERFLOW = 20
```

## Event Table Schema

```sql
CREATE TABLE events (
    id UUID PRIMARY KEY,
    type VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    meta JSONB NOT NULL,
    status VARCHAR DEFAULT 'pending',
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX idx_events_status ON events(status);
CREATE INDEX idx_events_type ON events(type);
```

## FOR UPDATE SKIP LOCKED

This pattern ensures concurrent consumers don't process the same event:

```sql
SELECT * FROM events
WHERE status = 'pending'
ORDER BY timestamp
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

- `FOR UPDATE` - Locks the row
- `SKIP LOCKED` - Skips rows locked by other consumers

## LISTEN/NOTIFY

Real-time event notification:

```sql
-- Publisher (automatic in EventStore)
NOTIFY events, 'event-id';

-- Subscriber
LISTEN events;
```

## Locking Backends

Events are processed with scope-based locking:

| Backend | Use Case |
|---------|----------|
| `memory` | Single instance, development |
| `postgres` | Multi-instance, production |

```python
# .env
LOCK_BACKEND=postgres  # or "memory"
```

## Migrations

```bash
# Create migration
make migrate name="add_new_column"

# Run migrations
make migrate-run

# Access DB directly
make db-shell
```

## Debugging Queries

```bash
make db-shell
```

```sql
-- Check pending events
SELECT COUNT(*) FROM events WHERE status = 'pending';

-- Check DLQ events
SELECT * FROM events WHERE status = 'failed' ORDER BY timestamp DESC LIMIT 10;

-- Check processing times
SELECT type, AVG(processed_at - created_at) as avg_time
FROM events WHERE processed_at IS NOT NULL
GROUP BY type;

-- Check locks
SELECT * FROM pg_locks WHERE relation = 'events'::regclass;
```

## Key Files

- `src/reflex/infra/store.py` - EventStore implementation
- `src/reflex/infra/database.py` - Database configuration
- `src/reflex/infra/locks.py` - Locking backends
- `tests/test_store.py` - Integration tests
