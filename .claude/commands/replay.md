---
description: Replay an event for debugging
argument-hint: "[event-id]"
---

# Replay Event

Replay event with ID: **$ARGUMENTS**

## Usage

```bash
# Using make (with event ID)
make replay ARGS="--event-id <event-id>"

# Using script directly
docker compose run --rm app python scripts/replay.py --event-id <event-id>
```

## What Replay Does

1. Fetches the event from the database by ID
2. Resets its status to `pending`
3. Event gets picked up by the agent loop
4. Processing happens with full logging

## Finding Event IDs

```bash
# From DLQ
curl http://localhost:8000/events/dlq | jq '.events[].id'

# From recent events (if you have DB access)
make db-shell
# Then: SELECT id, type, status FROM events ORDER BY timestamp DESC LIMIT 10;
```

## Replay Options

```bash
# Replay with verbose logging
make replay ARGS="--event-id <id> --verbose"

# Replay and skip trigger matching (force process)
make replay ARGS="--event-id <id> --force"
```

## Debugging Workflow

1. Find the problematic event ID (from DLQ or logs)
2. Review the event payload
3. Set breakpoints or add logging in the agent
4. Replay the event
5. Watch the logs: `make logs`

## Caution

- Replaying may cause duplicate side effects
- Use in development/staging, not production
- Consider idempotency of your agents

If an event ID is provided, replay that event and show the result.
