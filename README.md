# Reflex

Real-time AI agent primitives for continuous perception-action loops.

## Installation

```bash
pip install reflex
```

## Quick Start

```python
import asyncio
from reflex import (
    SQLiteEventStore,
    DecisionContext,
    WebSocketEvent,
)

async def main():
    # Initialize store
    store = SQLiteEventStore()
    await store.init()

    # Publish an event
    event = WebSocketEvent(
        source="ws:client1",
        connection_id="conn-123",
        content="Hello, world!",
    )
    await store.publish(event)

    # Subscribe to events
    async for event, token in store.subscribe():
        print(f"Received: {event.type} from {event.source}")
        await store.ack(token)
        break

asyncio.run(main())
```

## Core Primitives

- **Event types** — Pydantic models with discriminated unions
- **EventStore** — Persistence, replay, acknowledgment
- **DecisionContext** — Working memory that accumulates between actions
- **ReflexDeps** — Typed dependency container for PydanticAI agents
- **ScopedLocks** — Prevent concurrent actions for the same scope

## License

MIT
