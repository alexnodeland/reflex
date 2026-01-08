# Reflex Agents Skill

Apply this knowledge when building agents, working with triggers/filters, or debugging agent behavior.

## Agent Architecture

Agents are the core processing units that react to events. They use PydanticAI for LLM integration.

### Agent Types

| Base Class | Use Case | LLM |
|------------|----------|-----|
| `BaseAgent[T]` | LLM-powered with structured output | Yes |
| `SimpleAgent` | Event processing without LLM | No |

## BaseAgent Pattern

```python
from pydantic import BaseModel
from reflex.agent.base import BaseAgent
from reflex.agent.filters import TypeFilter
from reflex.agent.triggers import trigger

class MyOutput(BaseModel):
    response: str
    confidence: float

@trigger("my_agent", filter=TypeFilter(types=["my.event"]))
class MyAgent(BaseAgent[MyOutput]):
    output_type = MyOutput

    def get_system_prompt(self) -> str:
        return "You are a helpful assistant."

    def get_user_prompt(self, ctx: AgentContext) -> str:
        return ctx.event.content

    async def process_result(self, result: MyOutput, ctx: AgentContext) -> None:
        # Handle the LLM output
        await ctx.publish(ResponseEvent(...))
```

## SimpleAgent Pattern

```python
from reflex.agent.base import SimpleAgent

@trigger("simple_agent", filter=TypeFilter(types=["my.event"]))
class MySimpleAgent(SimpleAgent):
    async def handle(self, ctx: AgentContext) -> None:
        event = ctx.event
        # Process without LLM
        await ctx.deps.http.post(...)
```

## Filters

Filters determine which events trigger which agents.

### Built-in Filters

| Filter | Purpose |
|--------|---------|
| `TypeFilter` | Match by event type |
| `SourceFilter` | Match by source pattern (regex) |
| `KeywordFilter` | Match by content keywords |
| `RateLimitFilter` | Rate limiting (stateful) |
| `DedupeFilter` | Deduplication (stateful) |

### Filter Composition

```python
# AND - both must match
filter = TypeFilter(types=["ws.message"]) & SourceFilter(pattern=r"ws:vip-.*")

# OR - either matches
filter = type_filter("ws.message") | type_filter("http.request")

# NOT - negation
filter = ~TypeFilter(types=["lifecycle"])
```

### Factory Functions

```python
from reflex.agent.filters import (
    type_filter, source_filter, keyword_filter,
    rate_limit_filter, dedupe_filter,
    all_of, any_of, not_matching,
)

filter = all_of(
    type_filter("ws.message"),
    source_filter(r"ws:admin-.*"),
    rate_limit_filter(100, 60),
)
```

## Triggers

Triggers connect filters to agents.

### Decorator Style

```python
@trigger(
    name="my_trigger",
    filter=TypeFilter(types=["ws.message"]),
    scope_key=lambda e: e.connection_id,  # Locking scope
    priority=10,  # Higher = runs first
)
class MyAgent(SimpleAgent):
    ...
```

### Manual Registration

```python
from reflex.agent.triggers import Trigger, register_trigger

trigger = Trigger(
    name="my_trigger",
    filter=my_filter,
    agent=MyAgent(),
    scope_key=lambda e: e.source,
)
register_trigger(trigger)
```

## Agent Context

Agents receive `AgentContext` with:

```python
ctx.event      # The triggering event
ctx.deps       # ReflexDeps (store, http, db, scope)
ctx.publish()  # Publish derived events
ctx.derive_event()  # Get trace context for derived events
```

## Dependencies (ReflexDeps)

```python
ctx.deps.store   # EventStore - publish/subscribe
ctx.deps.http    # AsyncClient - HTTP requests
ctx.deps.db      # AsyncSession - database access
ctx.deps.scope   # Current scope key
```

## Key Files

- `src/reflex/agent/base.py` - Agent base classes
- `src/reflex/agent/filters.py` - Filter implementations
- `src/reflex/agent/triggers.py` - Trigger system
- `src/reflex/core/context.py` - AgentContext
- `src/reflex/core/deps.py` - ReflexDeps
