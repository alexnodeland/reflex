---
description: Scaffold a trigger connecting a filter to an agent
argument-hint: "[trigger-name]"
---

# Create New Trigger

Create a new trigger named: **$ARGUMENTS**

## Requirements

Triggers connect event filters to agents. There are two approaches:

## Approach 1: Decorator (Recommended)

Apply `@trigger` decorator to an agent class:

```python
from reflex.agent.base import SimpleAgent
from reflex.agent.filters import TypeFilter, SourceFilter
from reflex.agent.triggers import trigger


@trigger(
    name="my_trigger",
    filter=TypeFilter(types=["ws.message"]) & SourceFilter(pattern=r"ws:vip-.*"),
    scope_key=lambda e: f"user:{e.connection_id}",
    priority=10,  # Higher = runs first
)
class MyAgent(SimpleAgent):
    async def handle(self, ctx: AgentContext) -> None:
        ...
```

## Approach 2: Manual Registration

Create and register a Trigger instance:

```python
from reflex.agent.filters import TypeFilter
from reflex.agent.triggers import Trigger, register_trigger

# Create trigger
my_trigger = Trigger(
    name="my_trigger",
    filter=TypeFilter(types=["ws.message", "http.request"]),
    agent=MyAgent(),
    scope_key=lambda e: e.source,
    priority=0,
)

# Register it
register_trigger(my_trigger)
```

## Trigger Parameters

| Parameter | Description |
|-----------|-------------|
| `name` | Unique identifier for the trigger |
| `filter` | EventFilter that determines matching events |
| `agent` | Agent instance to execute on match |
| `scope_key` | Function to extract locking scope from event |
| `priority` | Execution order (higher = first), default 0 |

## Scope Key Examples

```python
# Per-source (default)
scope_key=lambda e: e.source

# Per-user (for WebSocket events)
scope_key=lambda e: f"user:{e.connection_id}"

# Per-session
scope_key=lambda e: e.meta.correlation_id or e.source

# Global (all events serialized)
scope_key=lambda e: "global"
```

## Filter Composition Examples

```python
# Multiple event types
filter=TypeFilter(types=["ws.message", "http.request"])

# Type AND source pattern
filter=TypeFilter(types=["ws.message"]) & SourceFilter(pattern=r"ws:admin-.*")

# Exclude lifecycle events
filter=TypeFilter(types=["ws.message"]) & ~TypeFilter(types=["lifecycle"])

# Rate limited
filter=TypeFilter(types=["api.call"]) & RateLimitFilter(max_events=100, window_seconds=60)
```

## Checklist

- [ ] Choose unique trigger name
- [ ] Compose appropriate filter
- [ ] Set scope_key for concurrency control
- [ ] Set priority if ordering matters
- [ ] Register trigger (decorator or manual)
