# Operations

Managing Reflex in production.

## Health Monitoring

### Basic Health Check

```bash
curl http://localhost:8000/health
```

```json
{"status": "healthy"}
```

### Detailed Health Check

```bash
curl http://localhost:8000/health/detailed
```

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

!!! tip "Load Balancer Health Checks"
    Use `/health` for load balancer probes (fast, simple response).
    Use `/health/detailed` for monitoring dashboards.

## Dead-Letter Queue (DLQ)

Events that fail after max retries move to the DLQ for manual intervention.

### List DLQ Events

```bash
python scripts/dlq.py list
```

### Retry Events

=== "Single Event"

    ```bash
    python scripts/dlq.py retry <event-id>
    ```

=== "All Events"

    ```bash
    python scripts/dlq.py retry-all
    ```

!!! warning "Before Retrying"
    Investigate why events failed before retrying. Check:

    - Application logs for error details
    - Event payload for malformed data
    - External service availability

## Event Replay

Replay historical events for debugging or reprocessing:

```bash
python scripts/replay.py
```

Use cases:

- Debugging agent behavior with specific events
- Reprocessing events after bug fixes
- Testing new trigger configurations

## Observability

Reflex integrates with [Logfire](https://pydantic.dev/logfire) for observability.

### Automatic Tracing

Traces are captured automatically for:

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

Set `LOGFIRE_TOKEN` in your environment:

```bash
LOGFIRE_TOKEN=your-token-here
```

## Runbook

### High DLQ Count

!!! danger "Symptoms"
    `/health/detailed` shows high DLQ count

**Steps:**

1. Check recent deployments for bugs
2. Review DLQ events: `python scripts/dlq.py list`
3. Check external service status
4. Fix root cause before retrying

### High Event Latency

!!! warning "Symptoms"
    Events taking long to process

**Steps:**

1. Check agent loop logs for slow operations
2. Review Logfire traces for bottlenecks
3. Consider scaling horizontally
4. Check database query performance

### Database Connection Exhaustion

!!! danger "Symptoms"
    Connection pool errors in logs

**Steps:**

1. Check `DB_POOL_MAX` vs running instances
2. Verify PostgreSQL `max_connections`
3. Look for connection leaks (unclosed sessions)
4. Increase pool size or reduce instances
