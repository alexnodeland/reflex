---
description: Inspect dead-letter queue for failed events
---

# Inspect Dead-Letter Queue

View failed events in the dead-letter queue.

## Quick Commands

```bash
# Using the script
make dlq

# Using API
curl http://localhost:8000/events/dlq?limit=100
```

## Response Format

```json
{
  "count": 5,
  "events": [
    {
      "id": "event-uuid",
      "type": "ws.message",
      "source": "ws:client-123",
      "timestamp": "2024-01-15T10:30:00Z",
      "status": "failed",
      "error": "Processing timeout",
      "retry_count": 3,
      "last_retry": "2024-01-15T10:35:00Z"
    }
  ]
}
```

## Retry a Failed Event

```bash
# Get the event ID from the DLQ list
curl -X POST http://localhost:8000/events/dlq/{event-id}/retry
```

Or use the `/replay` command for detailed replay.

## Using Bruno

```bash
# List DLQ
bru run bruno/events/list-dlq.bru --env docker

# Retry (after running list to set event ID)
bru run bruno/events/retry-dlq.bru --env docker
```

## Common DLQ Scenarios

### Processing Errors
- Agent threw an exception
- LLM call failed
- External API timeout

### Poison Messages
- Invalid event format
- Missing required fields
- Deserialization errors

## DLQ Management

Events enter DLQ after max retries (default: 3 with exponential backoff).

To investigate:
1. List DLQ events
2. Check error messages
3. Review event payload
4. Fix underlying issue
5. Retry or discard

List the current DLQ contents and summarize any patterns in failures.
