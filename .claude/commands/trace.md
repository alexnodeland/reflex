---
description: Trace an event through the system
argument-hint: "[event-id]"
---

# Trace Event Flow

Trace event with ID: **$ARGUMENTS**

## Event Lifecycle

```
1. PUBLISH    → Event created, stored in DB
2. NOTIFY     → PostgreSQL LISTEN/NOTIFY fires
3. SUBSCRIBE  → Consumer picks up event (FOR UPDATE SKIP LOCKED)
4. TRIGGER    → Filter matches, agent selected
5. EXECUTE    → Agent processes event
6. ACK/NACK   → Success (ack) or failure (nack → retry/DLQ)
```

## Tracing via Logs

```bash
# Watch logs for specific event
make logs 2>&1 | grep "<event-id>"

# Or with docker compose
docker compose logs -f app | grep "<event-id>"
```

## Tracing via Database

```bash
make db-shell
```

```sql
-- Find event and its status
SELECT id, type, source, status, retry_count, created_at, processed_at
FROM events
WHERE id = '<event-id>';

-- Check event history/transitions
SELECT * FROM event_logs WHERE event_id = '<event-id>' ORDER BY timestamp;
```

## Tracing via Logfire

If Logfire is configured, traces are automatically captured:
1. Go to your Logfire dashboard
2. Search for `event_id:<event-id>`
3. View the full trace with spans for:
   - `event.publish`
   - `event.subscribe`
   - `agent.run`
   - `event.ack` / `event.nack`

## Trace Fields

Events carry trace context in `meta`:
```json
{
  "meta": {
    "trace_id": "unique-trace-id",
    "correlation_id": "links-related-events",
    "causation_id": "parent-event-id"
  }
}
```

## Find Related Events

```sql
-- Find all events in same trace
SELECT * FROM events WHERE meta->>'trace_id' = '<trace-id>';

-- Find events caused by this one
SELECT * FROM events WHERE meta->>'causation_id' = '<event-id>';
```

If an event ID is provided, trace it through the system and report its status at each stage.
