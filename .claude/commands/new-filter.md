---
description: Scaffold a custom event filter (stateless or stateful)
argument-hint: "[filter-name]"
---

# Create New Filter

Create a new filter named: **$ARGUMENTS**

## Requirements

1. Add to `src/reflex/agent/filters.py` or create a new module
2. Choose filter type:
   - **Stateless** - Simple matching logic (use `@dataclass`)
   - **Stateful** - Tracks state across events (use `class` with `__init__`)

## Stateless Filter Pattern

```python
from dataclasses import dataclass
from reflex.agent.filters import EventFilter

@dataclass
class MyCustomFilter(EventFilter):
    """Filter events by custom criteria.

    Example:
        filter = MyCustomFilter(threshold=10)
        if filter.matches(event):
            # Event matches criteria
    """

    threshold: int

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        """Check if event matches the filter criteria."""
        # Access event fields
        value = getattr(event, "some_field", 0)
        return value >= self.threshold
```

## Stateful Filter Pattern

```python
from reflex.agent.filters import EventFilter

class MyStatefulFilter(EventFilter):
    """Filter with internal state tracking.

    Example:
        filter = MyStatefulFilter(window_seconds=60)
    """

    def __init__(self, window_seconds: float) -> None:
        self.window_seconds = window_seconds
        self._state: list[datetime] = []

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        """Check event and update internal state."""
        now = datetime.now(UTC)
        # Update state
        self._state.append(now)
        # Clean old entries
        cutoff = now - timedelta(seconds=self.window_seconds)
        self._state = [t for t in self._state if t >= cutoff]
        # Return match result
        return len(self._state) <= 10
```

## Factory Function Pattern

```python
def my_custom_filter(threshold: int) -> MyCustomFilter:
    """Create a MyCustomFilter.

    Example:
        filter = my_custom_filter(10)
    """
    return MyCustomFilter(threshold=threshold)
```

## Filter Composition

Filters support boolean operators:
```python
# AND - both must match
combined = TypeFilter(types=["ws.message"]) & MyCustomFilter(threshold=5)

# OR - either can match
combined = filter_a | filter_b

# NOT - negation
combined = ~TypeFilter(types=["lifecycle"])
```

## Checklist

- [ ] Inherit from `EventFilter`
- [ ] Implement `matches(self, event, context)` method
- [ ] Use `@dataclass` for stateless filters
- [ ] Add docstring with example usage
- [ ] Create factory function for convenience
- [ ] Add to module exports

After creating, show how to compose it with existing filters.
