"""Unified event filtering for trigger matching.

Filters determine which events should trigger which agents.
They support composition for complex matching logic via:
- Boolean operators: & (and), | (or), ~ (not)
- Convenience functions: all_of(), any_of(), not_matching()

All filters inherit from EventFilter and implement matches() which
optionally accepts a FilterContext for stateful filtering.
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
    from reflex.core.events import Event


def _empty_event_list() -> list[Event]:
    """Factory for empty event list with correct type annotation."""
    return []


def _empty_metadata() -> dict[str, Any]:
    """Factory for empty metadata dict."""
    return {}


@dataclass
class FilterContext:
    """Context for stateful filters.

    Provides event history and metadata for filters that need
    to track state across multiple filter invocations.

    Attributes:
        events: List of events seen so far
        last_action_time: When an action was last taken
        metadata: Arbitrary metadata for filter state
    """

    events: list[Event] = field(default_factory=_empty_event_list)
    last_action_time: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=_empty_metadata)


class EventFilter(ABC):
    """Base class for event filters.

    Filters are used by triggers to determine if an event
    should cause an agent to execute.

    Supports composition via boolean operators:
        type_filter & source_filter  # Both must match
        type_filter | source_filter  # Either can match
        ~type_filter                 # Negation

    Example:
        filter = TypeFilter(types=["ws.message"]) & SourceFilter(pattern=r"ws:vip-.*")
        if filter.matches(event):
            # Handle VIP websocket messages
    """

    @abstractmethod
    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        """Check if the event matches this filter.

        Args:
            event: The event to check
            context: Optional context for stateful filters

        Returns:
            True if the event matches, False otherwise
        """
        ...

    def __and__(self, other: EventFilter) -> EventFilter:
        """Combine filters with AND logic using & operator."""
        return AndFilter(filters=[self, other])

    def __or__(self, other: EventFilter) -> EventFilter:
        """Combine filters with OR logic using | operator."""
        return OrFilter(filters=[self, other])

    def __invert__(self) -> EventFilter:
        """Negate filter using ~ operator."""
        return NotFilter(filter=self)


@dataclass
class TypeFilter(EventFilter):
    """Filter events by type.

    Matches events where event.type equals one of the specified types.

    Example:
        filter = TypeFilter(types=["ws.message", "http.request"])
        filter.matches(ws_event)  # True if ws_event.type == "ws.message"
    """

    types: list[str]

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
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

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
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

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        """Check if all child filters match."""
        return all(f.matches(event, context) for f in self.filters)


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

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        """Check if any child filter matches."""
        return any(f.matches(event, context) for f in self.filters)


@dataclass
class NotFilter(EventFilter):
    """Negate a filter.

    Matches when the child filter does NOT match.

    Example:
        filter = NotFilter(filter=TypeFilter(types=["lifecycle"]))
    """

    filter: EventFilter

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        """Check if child filter does NOT match."""
        return not self.filter.matches(event, context)


@dataclass
class KeywordFilter(EventFilter):
    """Filter by keyword in event content.

    Searches the event's JSON representation for keyword matches.

    Example:
        filter = KeywordFilter(keywords=["error", "exception"])
        if filter.matches(event):
            # Event contains error-related content
    """

    keywords: list[str]
    case_sensitive: bool = False

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        """Check if any keyword is found in event content."""
        content = event.model_dump_json()
        if not self.case_sensitive:
            content = content.lower()
            return any(kw.lower() in content for kw in self.keywords)
        return any(kw in content for kw in self.keywords)


class RateLimitFilter(EventFilter):
    """Filter that rate-limits matching events.

    Accepts the first `max_events` events within the window,
    then rejects until the window moves forward.

    Example:
        filter = RateLimitFilter(max_events=100, window_seconds=60)
        if filter.matches(event):
            # Event is within rate limit
    """

    def __init__(self, max_events: int, window_seconds: float) -> None:
        """Initialize rate limit filter.

        Args:
            max_events: Maximum events allowed in the window
            window_seconds: Time window in seconds
        """
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._timestamps: list[datetime] = []

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        """Check if event is within rate limit."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Remove expired timestamps
        self._timestamps = [ts for ts in self._timestamps if ts >= cutoff]

        if len(self._timestamps) >= self.max_events:
            return False

        self._timestamps.append(now)
        return True


class DedupeFilter(EventFilter):
    """Filter that deduplicates events by key.

    Events with the same key are rejected within the time window.

    Example:
        filter = DedupeFilter(key_func=lambda e: e.id, window_seconds=300)
        if filter.matches(event):
            # Event is not a duplicate
    """

    def __init__(
        self,
        key_func: Callable[[Event], Any],
        window_seconds: float | None = None,
        max_keys: int = 10000,
    ) -> None:
        """Initialize dedupe filter.

        Args:
            key_func: Function to extract deduplication key from event
            window_seconds: Time window for deduplication (None = forever)
            max_keys: Maximum keys to track (LRU eviction)
        """
        self.key_func = key_func
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._seen: OrderedDict[Any, datetime] = OrderedDict()

    def matches(self, event: Event, context: FilterContext | None = None) -> bool:
        """Check if event is not a duplicate."""
        now = datetime.now(UTC)
        key = self.key_func(event)

        # Clean expired keys if window is set
        if self.window_seconds is not None:
            cutoff = now - timedelta(seconds=self.window_seconds)
            expired = [k for k, ts in self._seen.items() if ts < cutoff]
            for k in expired:
                del self._seen[k]

        # Check if key was seen
        if key in self._seen:
            # Move to end (most recent)
            self._seen.move_to_end(key)
            self._seen[key] = now
            return False

        # Add new key
        self._seen[key] = now

        # LRU eviction if over max
        while len(self._seen) > self.max_keys:
            self._seen.popitem(last=False)

        return True


# --- Convenience factory functions ---


def type_filter(*types: str) -> TypeFilter:
    """Create a TypeFilter for the given event types.

    Example:
        filter = type_filter("ws.message", "http.request")
    """
    return TypeFilter(types=list(types))


def source_filter(pattern: str) -> SourceFilter:
    """Create a SourceFilter for the given source pattern.

    Example:
        filter = source_filter(r"ws:client-.*")
    """
    return SourceFilter(pattern=pattern)


def keyword_filter(*keywords: str, case_sensitive: bool = False) -> KeywordFilter:
    """Create a KeywordFilter for the given keywords.

    Example:
        filter = keyword_filter("error", "exception", case_sensitive=False)
    """
    return KeywordFilter(keywords=list(keywords), case_sensitive=case_sensitive)


def rate_limit_filter(max_events: int, window_seconds: float) -> RateLimitFilter:
    """Create a RateLimitFilter.

    Example:
        filter = rate_limit_filter(100, 60)  # Max 100 events per minute
    """
    return RateLimitFilter(max_events=max_events, window_seconds=window_seconds)


def dedupe_filter(
    key_func: Callable[[Event], Any],
    window_seconds: float | None = None,
    max_keys: int = 10000,
) -> DedupeFilter:
    """Create a DedupeFilter.

    Example:
        filter = dedupe_filter(lambda e: e.id, window_seconds=300)
    """
    return DedupeFilter(key_func=key_func, window_seconds=window_seconds, max_keys=max_keys)


def all_of(*filters: EventFilter) -> AndFilter:
    """Create an AndFilter combining all given filters.

    Example:
        filter = all_of(type_filter("ws.message"), source_filter(r"ws:vip-.*"))
    """
    return AndFilter(filters=list(filters))


def any_of(*filters: EventFilter) -> OrFilter:
    """Create an OrFilter combining all given filters.

    Example:
        filter = any_of(type_filter("ws.message"), type_filter("http.request"))
    """
    return OrFilter(filters=list(filters))


def not_matching(filter: EventFilter) -> NotFilter:
    """Create a NotFilter negating the given filter.

    Example:
        filter = not_matching(type_filter("lifecycle"))
    """
    return NotFilter(filter=filter)


# --- Backward compatibility aliases ---
# These maintain compatibility with the old function-based Filter type

# Type alias preserved for backward compatibility
# New code should use the class-based filters directly
Filter = Callable[["Event", Any], bool]


def event_type_filter(*types: str) -> Callable[[Event, Any], bool]:
    """Create a filter function that matches events by type.

    This is a backward-compatible wrapper around TypeFilter.

    Args:
        *types: Event types to match

    Returns:
        Filter function compatible with old DecisionContext pattern
    """
    filter_instance = TypeFilter(types=list(types))

    def _filter(event: Event, ctx: Any) -> bool:
        return filter_instance.matches(event)

    return _filter


def all_filters(*filters: Callable[[Event, Any], bool]) -> Callable[[Event, Any], bool]:
    """Combine filter functions with AND logic.

    Backward-compatible function combinator.
    """

    def _filter(event: Event, ctx: Any) -> bool:
        return all(f(event, ctx) for f in filters)

    return _filter


def any_filter(*filters: Callable[[Event, Any], bool]) -> Callable[[Event, Any], bool]:
    """Combine filter functions with OR logic.

    Backward-compatible function combinator.
    """

    def _filter(event: Event, ctx: Any) -> bool:
        return any(f(event, ctx) for f in filters)

    return _filter
