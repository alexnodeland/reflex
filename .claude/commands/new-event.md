---
description: Scaffold a new event type with EventRegistry decorator
argument-hint: "[event-name]"
---

# Create New Event Type

Create a new event type named: **$ARGUMENTS**

## Requirements

1. Create the event class in `src/reflex/core/events.py` (or a new module if specified)
2. Follow this pattern:

```python
@EventRegistry.register
class MyNewEvent(BaseEvent):
    """Description of what this event represents."""

    type: Literal["my.new"] = "my.new"
    # Add custom fields here
    custom_field: str
    optional_field: int | None = None
```

## Checklist

- [ ] Use `@EventRegistry.register` decorator
- [ ] Define `type` field with `Literal` type matching the default value
- [ ] Use dot notation for type (e.g., `user.created`, `order.completed`)
- [ ] Add docstring explaining the event's purpose
- [ ] Use proper type hints for all fields
- [ ] Add `Field()` with descriptions for complex fields
- [ ] Import `Literal` from `typing`

## Event Naming Conventions

- Use lowercase with dots: `domain.action` (e.g., `user.signup`, `payment.failed`)
- Keep it descriptive but concise
- Group related events by prefix (e.g., `ws.*`, `http.*`, `timer.*`)

After creating the event, suggest a test case for it.
