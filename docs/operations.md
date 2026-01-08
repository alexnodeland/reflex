# Operations

Managing Reflex in production.

## Dead-Letter Queue (DLQ)

Failed events (after max retries with exponential backoff) move to the DLQ.

```bash
# List DLQ events
python scripts/dlq.py list

# Retry a specific event
python scripts/dlq.py retry <event-id>

# Retry all DLQ events
python scripts/dlq.py retry-all
```

## Event Replay

Replay events for debugging or reprocessing:

```bash
python scripts/replay.py
```

## Health Monitoring

### Basic Health Check

```bash
curl http://localhost:8000/health
```

### Detailed Health Check

```bash
curl http://localhost:8000/health/detailed
```

Response:

```json
{
  "status": "healthy",
  "indicators": [
    {"name": "database", "status": "healthy", "latency_ms": 1.5},
    {"name": "event_queue", "status": "healthy", "message": "42 pending"},
    {"name": "dlq", "status": "healthy", "message": "0 in DLQ"}
  ]
}
```

## Observability

Reflex is pre-configured for Logfire observability.

### Automatic Tracing

Traces are automatic for:

- HTTP requests
- WebSocket connections
- Event store operations
- Agent tool calls

### Custom Spans

```python
import logfire

with logfire.span("my-operation", key=value):
    # Your code here
    ...
```

### Configuration

Set `LOGFIRE_TOKEN` in your environment to enable observability.
