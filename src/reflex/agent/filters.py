"""Event filtering for trigger matching.

Filters determine which events should trigger which agents.
They support composition for complex matching logic.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reflex.core.events import Event


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
