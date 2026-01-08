# Reflex Events Skill

Apply this knowledge when working with events, debugging event flow, or asking about event types.

## Event System Overview

Reflex uses an event-driven architecture with PostgreSQL LISTEN/NOTIFY for real-time pub/sub.

### Event Lifecycle

```
1. PUBLISH    → EventStore.publish() persists to DB + fires NOTIFY
2. SUBSCRIBE  → Consumer receives via EventStore.subscribe()
3. PROCESS    → Trigger matches event to agent
4. ACK/NACK   → Success (ack) removes event, failure (nack) retries
```

## Event Structure

All events inherit from `BaseEvent`:

```python
class BaseEvent(BaseModel):
    id: str                    # UUID, auto-generated
    timestamp: datetime        # UTC, auto-generated
    source: str               # Origin identifier (e.g., "ws:client-123")
    meta: EventMeta           # Trace context

class EventMeta(BaseModel):
    trace_id: str             # Unique trace ID
    correlation_id: str | None # Links related events
    causation_id: str | None   # Parent event that caused this
```

## Creating Custom Events

```python
from typing import Literal
from reflex.core.events import BaseEvent, EventRegistry

@EventRegistry.register
class MyCustomEvent(BaseEvent):
    """Description of the event."""

    type: Literal["my.custom"] = "my.custom"
    custom_field: str
    optional_field: int | None = None
```

### Requirements:
- Use `@EventRegistry.register` decorator
- Define `type` with `Literal` matching the default value
- Use dot notation: `domain.action` (e.g., `user.signup`)

## Built-in Event Types

| Type | Class | Description |
|------|-------|-------------|
| `ws.message` | `WebSocketEvent` | WebSocket message received |
| `http.request` | `HTTPEvent` | HTTP request event |
| `timer.tick` | `TimerEvent` | Periodic timer event |
| `lifecycle` | `LifecycleEvent` | System lifecycle events |

## Event Validation

Events use Pydantic discriminated unions for O(1) validation:

```python
# Parse any registered event type
event = EventRegistry.parse(data)

# Get dynamic union type
DynamicEvent = get_event_union()
```

## Publishing Events

```python
# From agent context
await ctx.publish(MyCustomEvent(
    source="agent:my-agent",
    custom_field="value",
    **ctx.derive_event(),  # Preserves trace context
))

# From EventStore directly
await store.publish(event)
```

## Trace Context

Preserve causation chain with `derive_event()`:
```python
derived = ctx.derive_event()
# Returns: {"meta": EventMeta(correlation_id=..., causation_id=current_event.id)}
```

## Key Files

- `src/reflex/core/events.py` - Event types and registry
- `src/reflex/infra/store.py` - EventStore implementation
- `tests/test_events.py` - Event tests
