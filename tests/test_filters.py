"""Tests for event filters."""

from reflex.agent.filters import (
    AndFilter,
    NotFilter,
    OrFilter,
    SourceFilter,
    TypeFilter,
    all_filters,
    all_of,
    any_filter,
    any_of,
    dedupe_filter,
    event_type_filter,
    keyword_filter,
    not_matching,
    rate_limit_filter,
    source_filter,
    type_filter,
)
from reflex.core.context import DecisionContext
from reflex.core.events import HTTPEvent, TimerEvent, WebSocketEvent


class TestTypeFilter:
    """Tests for TypeFilter."""

    def test_single_type_match(self) -> None:
        """Test matching a single event type."""
        f = TypeFilter(types=["ws.message"])
        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        assert f.matches(event)

    def test_single_type_no_match(self) -> None:
        """Test not matching a different event type."""
        f = TypeFilter(types=["http.request"])
        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        assert not f.matches(event)

    def test_multiple_types_match(self) -> None:
        """Test matching one of multiple types."""
        f = TypeFilter(types=["ws.message", "http.request"])
        ws_event = WebSocketEvent(source="test", connection_id="1", content="hi")
        http_event = HTTPEvent(source="api", method="GET", path="/")
        assert f.matches(ws_event)
        assert f.matches(http_event)

    def test_convenience_function(self) -> None:
        """Test type_filter convenience function."""
        f = type_filter("ws.message", "http.request")
        assert isinstance(f, TypeFilter)
        assert f.types == ["ws.message", "http.request"]


class TestSourceFilter:
    """Tests for SourceFilter."""

    def test_exact_match(self) -> None:
        """Test exact source match."""
        f = SourceFilter(pattern=r"ws:client-123")
        event = WebSocketEvent(source="ws:client-123", connection_id="1", content="hi")
        assert f.matches(event)

    def test_pattern_match(self) -> None:
        """Test regex pattern match."""
        f = SourceFilter(pattern=r"ws:client-.*")
        event1 = WebSocketEvent(source="ws:client-123", connection_id="1", content="hi")
        event2 = WebSocketEvent(source="ws:client-456", connection_id="2", content="hi")
        assert f.matches(event1)
        assert f.matches(event2)

    def test_pattern_no_match(self) -> None:
        """Test pattern that doesn't match."""
        f = SourceFilter(pattern=r"ws:vip-.*")
        event = WebSocketEvent(source="ws:client-123", connection_id="1", content="hi")
        assert not f.matches(event)

    def test_convenience_function(self) -> None:
        """Test source_filter convenience function."""
        f = source_filter(r"api:.*")
        assert isinstance(f, SourceFilter)
        assert f.pattern == r"api:.*"


class TestAndFilter:
    """Tests for AndFilter."""

    def test_all_match(self) -> None:
        """Test when all filters match."""
        f = AndFilter(
            filters=[
                TypeFilter(types=["ws.message"]),
                SourceFilter(pattern=r"ws:client-.*"),
            ]
        )
        event = WebSocketEvent(source="ws:client-123", connection_id="1", content="hi")
        assert f.matches(event)

    def test_partial_match(self) -> None:
        """Test when only some filters match."""
        f = AndFilter(
            filters=[
                TypeFilter(types=["ws.message"]),
                SourceFilter(pattern=r"ws:vip-.*"),
            ]
        )
        event = WebSocketEvent(source="ws:client-123", connection_id="1", content="hi")
        assert not f.matches(event)

    def test_empty_filters(self) -> None:
        """Test with no filters (vacuous truth)."""
        f = AndFilter(filters=[])
        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        assert f.matches(event)

    def test_convenience_function(self) -> None:
        """Test all_of convenience function."""
        f = all_of(type_filter("ws.message"), source_filter(r"ws:.*"))
        assert isinstance(f, AndFilter)
        assert len(f.filters) == 2


class TestOrFilter:
    """Tests for OrFilter."""

    def test_first_matches(self) -> None:
        """Test when first filter matches."""
        f = OrFilter(
            filters=[
                TypeFilter(types=["ws.message"]),
                TypeFilter(types=["http.request"]),
            ]
        )
        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        assert f.matches(event)

    def test_second_matches(self) -> None:
        """Test when second filter matches."""
        f = OrFilter(
            filters=[
                TypeFilter(types=["timer.tick"]),
                TypeFilter(types=["ws.message"]),
            ]
        )
        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        assert f.matches(event)

    def test_none_match(self) -> None:
        """Test when no filters match."""
        f = OrFilter(
            filters=[
                TypeFilter(types=["timer.tick"]),
                TypeFilter(types=["http.request"]),
            ]
        )
        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        assert not f.matches(event)

    def test_empty_filters(self) -> None:
        """Test with no filters (vacuous falsity)."""
        f = OrFilter(filters=[])
        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        assert not f.matches(event)

    def test_convenience_function(self) -> None:
        """Test any_of convenience function."""
        f = any_of(type_filter("ws.message"), type_filter("http.request"))
        assert isinstance(f, OrFilter)
        assert len(f.filters) == 2


class TestNotFilter:
    """Tests for NotFilter."""

    def test_negates_match(self) -> None:
        """Test that NotFilter negates a matching filter."""
        f = NotFilter(filter=TypeFilter(types=["ws.message"]))
        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        assert not f.matches(event)

    def test_negates_no_match(self) -> None:
        """Test that NotFilter negates a non-matching filter."""
        f = NotFilter(filter=TypeFilter(types=["http.request"]))
        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        assert f.matches(event)

    def test_convenience_function(self) -> None:
        """Test not_matching convenience function."""
        f = not_matching(type_filter("lifecycle"))
        assert isinstance(f, NotFilter)


class TestCompositeFilters:
    """Tests for complex filter compositions."""

    def test_nested_and_or(self) -> None:
        """Test nested AND and OR filters."""
        # Match: (ws.message OR http.request) AND source matches ws:vip-*
        f = AndFilter(
            filters=[
                OrFilter(
                    filters=[
                        TypeFilter(types=["ws.message"]),
                        TypeFilter(types=["http.request"]),
                    ]
                ),
                SourceFilter(pattern=r"ws:vip-.*"),
            ]
        )

        vip_ws = WebSocketEvent(source="ws:vip-123", connection_id="1", content="hi")
        regular_ws = WebSocketEvent(source="ws:client-123", connection_id="2", content="hi")
        timer = TimerEvent(source="ws:vip-123", timer_name="test")

        assert f.matches(vip_ws)  # Matches type and source
        assert not f.matches(regular_ws)  # Matches type but not source
        assert not f.matches(timer)  # Doesn't match type

    def test_not_with_or(self) -> None:
        """Test NOT combined with OR."""
        # Match anything except lifecycle or timer events
        f = NotFilter(
            filter=OrFilter(
                filters=[
                    TypeFilter(types=["lifecycle"]),
                    TypeFilter(types=["timer.tick"]),
                ]
            )
        )

        ws = WebSocketEvent(source="test", connection_id="1", content="hi")
        timer = TimerEvent(source="test", timer_name="test")

        assert f.matches(ws)
        assert not f.matches(timer)


# --- Filter function tests ---


class TestKeywordFilter:
    """Tests for keyword_filter function."""

    def test_keyword_match(self) -> None:
        """Test matching keyword in event content."""
        ctx = DecisionContext()
        f = keyword_filter("error", "failed")

        event_match = WebSocketEvent(source="test", connection_id="1", content="An error occurred")
        event_no_match = WebSocketEvent(source="test", connection_id="1", content="Success")

        assert f(event_match, ctx)
        assert not f(event_no_match, ctx)

    def test_keyword_case_insensitive(self) -> None:
        """Test case insensitive keyword matching."""
        ctx = DecisionContext()
        f = keyword_filter("error", case_sensitive=False)

        event = WebSocketEvent(source="test", connection_id="1", content="ERROR in system")
        assert f(event, ctx)

    def test_keyword_case_sensitive(self) -> None:
        """Test case sensitive keyword matching."""
        ctx = DecisionContext()
        f = keyword_filter("Error", case_sensitive=True)

        event_match = WebSocketEvent(source="test", connection_id="1", content="Error occurred")
        event_no_match = WebSocketEvent(source="test", connection_id="1", content="error occurred")

        assert f(event_match, ctx)
        assert not f(event_no_match, ctx)

    def test_keyword_in_any_field(self) -> None:
        """Test keyword matching in any serialized field."""
        ctx = DecisionContext()
        f = keyword_filter("api-endpoint")

        event = WebSocketEvent(source="api-endpoint:123", connection_id="1", content="x")
        assert f(event, ctx)


class TestEventTypeFilter:
    """Tests for event_type_filter function."""

    def test_type_match(self) -> None:
        """Test matching event by type."""
        ctx = DecisionContext()
        f = event_type_filter("ws.message", "http.request")

        ws_event = WebSocketEvent(source="test", connection_id="1", content="hi")
        http_event = HTTPEvent(source="test", method="GET", path="/")
        timer_event = TimerEvent(source="test", timer_name="tick")

        assert f(ws_event, ctx)
        assert f(http_event, ctx)
        assert not f(timer_event, ctx)


class TestRateLimitFilter:
    """Tests for rate_limit_filter function."""

    def test_under_limit(self) -> None:
        """Test events under rate limit are accepted."""
        ctx = DecisionContext()
        f = rate_limit_filter(max_events=5, window_seconds=60)

        event = WebSocketEvent(source="test", connection_id="1", content="hi")

        # First 5 should pass
        for _ in range(5):
            assert f(event, ctx)

    def test_over_limit(self) -> None:
        """Test events over rate limit are rejected."""
        ctx = DecisionContext()
        f = rate_limit_filter(max_events=3, window_seconds=60)

        event = WebSocketEvent(source="test", connection_id="1", content="hi")

        # First 3 should pass
        assert f(event, ctx)
        assert f(event, ctx)
        assert f(event, ctx)

        # 4th should be rejected
        assert not f(event, ctx)


class TestDedupeFilter:
    """Tests for dedupe_filter function."""

    def test_first_event_passes(self) -> None:
        """Test first event with unique key passes."""
        ctx = DecisionContext()
        f = dedupe_filter(key_func=lambda e: e.id)

        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        assert f(event, ctx)

    def test_duplicate_rejected(self) -> None:
        """Test duplicate events are rejected."""
        ctx = DecisionContext()
        f = dedupe_filter(key_func=lambda e: e.id)

        event = WebSocketEvent(id="same-id", source="test", connection_id="1", content="hi")

        assert f(event, ctx)  # First pass
        assert not f(event, ctx)  # Duplicate rejected

    def test_different_keys_pass(self) -> None:
        """Test events with different keys pass."""
        ctx = DecisionContext()
        f = dedupe_filter(key_func=lambda e: e.id)

        event1 = WebSocketEvent(id="id-1", source="test", connection_id="1", content="hi")
        event2 = WebSocketEvent(id="id-2", source="test", connection_id="1", content="hi")

        assert f(event1, ctx)
        assert f(event2, ctx)

    def test_lru_eviction(self) -> None:
        """Test LRU eviction when max_keys exceeded."""
        ctx = DecisionContext()
        f = dedupe_filter(key_func=lambda e: e.id, max_keys=3)

        # Add 4 events to trigger eviction
        for i in range(4):
            event = WebSocketEvent(id=f"id-{i}", source="test", connection_id="1", content="hi")
            assert f(event, ctx)

        # First event should have been evicted
        event_first = WebSocketEvent(id="id-0", source="test", connection_id="1", content="hi")
        assert f(event_first, ctx)  # Should pass as it was evicted


class TestFilterFunctionComposition:
    """Tests for combining filter functions."""

    def test_all_filters_and(self) -> None:
        """Test all_filters combines with AND logic."""
        ctx = DecisionContext()
        f = all_filters(
            event_type_filter("ws.message"),
            keyword_filter("hello"),
        )

        matching = WebSocketEvent(source="test", connection_id="1", content="hello world")
        wrong_type = HTTPEvent(source="test", method="GET", path="/hello")
        wrong_content = WebSocketEvent(source="test", connection_id="1", content="bye")

        assert f(matching, ctx)
        assert not f(wrong_type, ctx)
        assert not f(wrong_content, ctx)

    def test_any_filter_or(self) -> None:
        """Test any_filter combines with OR logic."""
        ctx = DecisionContext()
        f = any_filter(
            event_type_filter("ws.message"),
            event_type_filter("http.request"),
        )

        ws_event = WebSocketEvent(source="test", connection_id="1", content="hi")
        http_event = HTTPEvent(source="test", method="GET", path="/")
        timer_event = TimerEvent(source="test", timer_name="tick")

        assert f(ws_event, ctx)
        assert f(http_event, ctx)
        assert not f(timer_event, ctx)
