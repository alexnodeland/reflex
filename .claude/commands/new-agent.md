---
description: Scaffold a new agent with trigger and filter setup
argument-hint: "[agent-name]"
---

# Create New Agent

Create a new agent named: **$ARGUMENTS**

## Requirements

1. Create the agent in `src/reflex/agent/` (new file or existing module)
2. Choose the appropriate base class:
   - `BaseAgent[T]` - For LLM-powered agents with structured output
   - `SimpleAgent` - For agents without LLM, just event processing

## BaseAgent Pattern (with LLM)

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from reflex.agent.base import BaseAgent
from reflex.agent.filters import TypeFilter
from reflex.agent.triggers import trigger

if TYPE_CHECKING:
    from reflex.core.context import AgentContext


class MyAgentOutput(BaseModel):
    """Structured output from the agent."""
    response: str
    confidence: float


@trigger(
    name="my_agent_trigger",
    filter=TypeFilter(types=["my.event.type"]),
    scope_key=lambda e: e.source,  # Scope for locking
)
class MyAgent(BaseAgent[MyAgentOutput]):
    """Description of what this agent does."""

    output_type = MyAgentOutput

    def get_system_prompt(self) -> str:
        return "You are a helpful assistant that..."

    def get_user_prompt(self, ctx: AgentContext) -> str:
        return f"Process this event: {ctx.event.model_dump_json()}"

    async def process_result(self, result: MyAgentOutput, ctx: AgentContext) -> None:
        # Publish derived events, update state, etc.
        pass
```

## SimpleAgent Pattern (no LLM)

```python
from reflex.agent.base import SimpleAgent
from reflex.agent.filters import TypeFilter
from reflex.agent.triggers import trigger


@trigger(
    name="my_simple_trigger",
    filter=TypeFilter(types=["my.event.type"]),
)
class MySimpleAgent(SimpleAgent):
    """Description of what this agent does."""

    async def handle(self, ctx: AgentContext) -> None:
        event = ctx.event
        # Process the event
        await ctx.deps.store.publish(...)
```

## Checklist

- [ ] Choose correct base class (BaseAgent vs SimpleAgent)
- [ ] Define output model if using BaseAgent
- [ ] Add `@trigger` decorator with appropriate filter
- [ ] Set `scope_key` for concurrent event handling
- [ ] Implement required methods
- [ ] Use `TYPE_CHECKING` for type-only imports
- [ ] Add docstrings

After creating, suggest integration tests using `mock_deps` fixture.
