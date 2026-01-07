"""Event filtering for trigger matching.

Filters determine which events should trigger which agents.
They support composition for complex matching logic.

There are two types of filters:
1. EventFilter (class-based) - stateless filters for trigger matching
2. Filter functions - stateful filters that work with DecisionContext
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from reflex.core.context import DecisionContext
    from reflex.core.events import Event

# Type alias for filter functions that work with DecisionContext
Filter = Callable[["Event", "DecisionContext"], bool]


class EventFilter(ABC):
    """Protocol for event filters.

    Filters are used by triggers to determine if an event
    should cause an agent to execute.
    """

    @abstractmethod
    def matches(self, event: Event) -> bool:
        """Check if the event matches this filter.

        Args:
            event: The event to check

        Returns:
            True if the event matches, False otherwise
        """
        ...


@dataclass
class TypeFilter(EventFilter):
    """Filter events by type.

    Matches events where event.type equals one of the specified types.

    Example:
        filter = TypeFilter(types=["ws.message", "http.request"])
        filter.matches(ws_event)  # True if ws_event.type == "ws.message"
    """

    types: list[str]

    def matches(self, event: Event) -> bool:
        """Check if event type is in the allowed types."""
        return event.type in self.types


@dataclass
class SourceFilter(EventFilter):
    """Filter events by source pattern.

    Matches events where event.source matches the regex pattern.

    Example:
        filter = SourceFilter(pattern=r"ws:client-.*")
        filter.matches(event)  # True if event.source matches pattern
    """

    pattern: str

    def __post_init__(self) -> None:
        """Compile the regex pattern."""
        self._compiled = re.compile(self.pattern)

    def matches(self, event: Event) -> bool:
        """Check if event source matches the pattern."""
        return bool(self._compiled.match(event.source))


@dataclass
class AndFilter(EventFilter):
    """Combine filters with AND logic.

    All child filters must match for this filter to match.

    Example:
        filter = AndFilter(filters=[
            TypeFilter(types=["ws.message"]),
            SourceFilter(pattern=r"ws:vip-.*"),
        ])
    """

    filters: list[EventFilter]

    def matches(self, event: Event) -> bool:
        """Check if all child filters match."""
        return all(f.matches(event) for f in self.filters)


@dataclass
class OrFilter(EventFilter):
    """Combine filters with OR logic.

    At least one child filter must match for this filter to match.

    Example:
        filter = OrFilter(filters=[
            TypeFilter(types=["ws.message"]),
            TypeFilter(types=["http.request"]),
        ])
    """

    filters: list[EventFilter]

    def matches(self, event: Event) -> bool:
        """Check if any child filter matches."""
        return any(f.matches(event) for f in self.filters)


@dataclass
class NotFilter(EventFilter):
    """Negate a filter.

    Matches when the child filter does NOT match.

    Example:
        filter = NotFilter(filter=TypeFilter(types=["lifecycle"]))
    """

    filter: EventFilter

    def matches(self, event: Event) -> bool:
        """Check if child filter does NOT match."""
        return not self.filter.matches(event)


# Convenience functions for filter composition


def type_filter(*types: str) -> TypeFilter:
    """Create a TypeFilter for the given event types."""
    return TypeFilter(types=list(types))


def source_filter(pattern: str) -> SourceFilter:
    """Create a SourceFilter for the given source pattern."""
    return SourceFilter(pattern=pattern)


def all_of(*filters: EventFilter) -> AndFilter:
    """Create an AndFilter combining all given filters."""
    return AndFilter(filters=list(filters))


def any_of(*filters: EventFilter) -> OrFilter:
    """Create an OrFilter combining all given filters."""
    return OrFilter(filters=list(filters))


def not_matching(filter: EventFilter) -> NotFilter:
    """Create a NotFilter negating the given filter."""
    return NotFilter(filter=filter)


# --- Filter functions (stateful, work with DecisionContext) ---


def keyword_filter(*keywords: str, case_sensitive: bool = False) -> Filter:
    """Create a filter that matches events containing any keyword.

    Searches the event's JSON representation for keyword matches.

    Args:
        *keywords: Keywords to search for
        case_sensitive: Whether matching is case-sensitive

    Returns:
        Filter function

    Example:
        filter = keyword_filter("error", "exception", "failed")
        if filter(event, ctx):
            # Event contains at least one keyword
    """
    search_keywords = keywords if case_sensitive else tuple(k.lower() for k in keywords)

    def _filter(event: Event, ctx: DecisionContext) -> bool:
        # Search in the JSON representation of the event
        event_str = event.model_dump_json()
        if not case_sensitive:
            event_str = event_str.lower()
        return any(kw in event_str for kw in search_keywords)

    return _filter


def event_type_filter(*types: str) -> Filter:
    """Create a filter that matches events by type.

    This is a functional version of TypeFilter for use with DecisionContext.

    Args:
        *types: Event types to match

    Returns:
        Filter function
    """
    type_set = set(types)

    def _filter(event: Event, ctx: DecisionContext) -> bool:
        return event.type in type_set

    return _filter


def _empty_datetime_list() -> list[datetime]:
    """Factory for empty datetime list with correct type annotation."""
    return []


@dataclass
class RateLimitState:
    """Internal state for rate limiting."""

    timestamps: list[datetime] = field(default_factory=_empty_datetime_list)


def rate_limit_filter(max_events: int, window_seconds: float) -> Filter:
    """Create a filter that caps events per time window.

    Accepts the first `max_events` events within the window,
    then rejects until the window moves forward.

    Args:
        max_events: Maximum events allowed in the window
        window_seconds: Time window in seconds

    Returns:
        Filter function

    Example:
        filter = rate_limit_filter(100, 60)  # Max 100 events per minute
        if filter(event, ctx):
            # Event is within rate limit
    """
    state = RateLimitState()

    def _filter(event: Event, ctx: DecisionContext) -> bool:
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=window_seconds)

        # Remove expired timestamps
        state.timestamps = [ts for ts in state.timestamps if ts >= cutoff]

        if len(state.timestamps) >= max_events:
            return False

        state.timestamps.append(now)
        return True

    return _filter


def dedupe_filter(
    key_func: Callable[[Event], Any],
    window_seconds: float | None = None,
    max_keys: int = 10000,
) -> Filter:
    """Create a filter that deduplicates events by key.

    Events with the same key (extracted by key_func) are rejected
    within the time window (or indefinitely if no window).

    Args:
        key_func: Function to extract deduplication key from event
        window_seconds: Time window for deduplication (None = forever)
        max_keys: Maximum keys to track (LRU eviction)

    Returns:
        Filter function

    Example:
        filter = dedupe_filter(lambda e: e.id, window_seconds=300)
        if filter(event, ctx):
            # Event is not a duplicate
    """
    # Use OrderedDict for LRU behavior
    seen: OrderedDict[Any, datetime] = OrderedDict()

    def _filter(event: Event, ctx: DecisionContext) -> bool:
        now = datetime.now(UTC)
        key = key_func(event)

        # Clean expired keys if window is set
        if window_seconds is not None:
            cutoff = now - timedelta(seconds=window_seconds)
            expired = [k for k, ts in seen.items() if ts < cutoff]
            for k in expired:
                del seen[k]

        # Check if key was seen
        if key in seen:
            # Move to end (most recent)
            seen.move_to_end(key)
            seen[key] = now
            return False

        # Add new key
        seen[key] = now

        # LRU eviction if over max
        while len(seen) > max_keys:
            seen.popitem(last=False)

        return True

    return _filter


def all_filters(*filters: Filter) -> Filter:
    """Combine filter functions with AND logic.

    All filters must return True for the combined filter to return True.

    Args:
        *filters: Filter functions to combine

    Returns:
        Combined filter function
    """

    def _filter(event: Event, ctx: DecisionContext) -> bool:
        return all(f(event, ctx) for f in filters)

    return _filter


def any_filter(*filters: Filter) -> Filter:
    """Combine filter functions with OR logic.

    At least one filter must return True for the combined filter to return True.

    Args:
        *filters: Filter functions to combine

    Returns:
        Combined filter function
    """

    def _filter(event: Event, ctx: DecisionContext) -> bool:
        return any(f(event, ctx) for f in filters)

    return _filter
