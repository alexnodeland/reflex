"""Tests for event filters."""

from reflex.agent.filters import (
    AndFilter,
    DedupeFilter,
    FilterContext,
    KeywordFilter,
    NotFilter,
    OrFilter,
    RateLimitFilter,
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


# --- Dunder method operator tests ---


class TestFilterOperators:
    """Tests for filter dunder method operators."""

    def test_and_operator(self) -> None:
        """Test & operator creates AndFilter."""
        f1 = TypeFilter(types=["ws.message"])
        f2 = SourceFilter(pattern=r"ws:.*")
        combined = f1 & f2

        assert isinstance(combined, AndFilter)

        event = WebSocketEvent(source="ws:client-123", connection_id="1", content="hi")
        assert combined.matches(event)

        wrong_source = WebSocketEvent(source="api:server", connection_id="1", content="hi")
        assert not combined.matches(wrong_source)

    def test_or_operator(self) -> None:
        """Test | operator creates OrFilter."""
        f1 = TypeFilter(types=["ws.message"])
        f2 = TypeFilter(types=["http.request"])
        combined = f1 | f2

        assert isinstance(combined, OrFilter)

        ws = WebSocketEvent(source="test", connection_id="1", content="hi")
        http = HTTPEvent(source="test", method="GET", path="/")
        timer = TimerEvent(source="test", timer_name="test")

        assert combined.matches(ws)
        assert combined.matches(http)
        assert not combined.matches(timer)

    def test_invert_operator(self) -> None:
        """Test ~ operator creates NotFilter."""
        f = TypeFilter(types=["lifecycle"])
        negated = ~f

        assert isinstance(negated, NotFilter)

        ws = WebSocketEvent(source="test", connection_id="1", content="hi")
        assert negated.matches(ws)

    def test_chained_operators(self) -> None:
        """Test chaining multiple operators."""
        # (ws.message | http.request) & ~lifecycle
        f = (type_filter("ws.message") | type_filter("http.request")) & ~type_filter("lifecycle")

        ws = WebSocketEvent(source="test", connection_id="1", content="hi")
        http = HTTPEvent(source="test", method="GET", path="/")
        timer = TimerEvent(source="test", timer_name="test")

        assert f.matches(ws)
        assert f.matches(http)
        assert not f.matches(timer)


# --- Class-based filter tests ---


class TestKeywordFilter:
    """Tests for KeywordFilter class."""

    def test_keyword_match(self) -> None:
        """Test matching keyword in event content."""
        f = KeywordFilter(keywords=["error", "failed"])

        event_match = WebSocketEvent(source="test", connection_id="1", content="An error occurred")
        event_no_match = WebSocketEvent(source="test", connection_id="1", content="Success")

        assert f.matches(event_match)
        assert not f.matches(event_no_match)

    def test_keyword_case_insensitive(self) -> None:
        """Test case insensitive keyword matching."""
        f = KeywordFilter(keywords=["error"], case_sensitive=False)

        event = WebSocketEvent(source="test", connection_id="1", content="ERROR in system")
        assert f.matches(event)

    def test_keyword_case_sensitive(self) -> None:
        """Test case sensitive keyword matching."""
        f = KeywordFilter(keywords=["Error"], case_sensitive=True)

        event_match = WebSocketEvent(source="test", connection_id="1", content="Error occurred")
        event_no_match = WebSocketEvent(source="test", connection_id="1", content="error occurred")

        assert f.matches(event_match)
        assert not f.matches(event_no_match)

    def test_keyword_in_any_field(self) -> None:
        """Test keyword matching in any serialized field."""
        f = KeywordFilter(keywords=["api-endpoint"])

        event = WebSocketEvent(source="api-endpoint:123", connection_id="1", content="x")
        assert f.matches(event)

    def test_convenience_function(self) -> None:
        """Test keyword_filter convenience function."""
        f = keyword_filter("error", "exception")
        assert isinstance(f, KeywordFilter)
        assert f.keywords == ["error", "exception"]


class TestRateLimitFilter:
    """Tests for RateLimitFilter class."""

    def test_under_limit(self) -> None:
        """Test events under rate limit are accepted."""
        f = RateLimitFilter(max_events=5, window_seconds=60)

        event = WebSocketEvent(source="test", connection_id="1", content="hi")

        # First 5 should pass
        for _ in range(5):
            assert f.matches(event)

    def test_over_limit(self) -> None:
        """Test events over rate limit are rejected."""
        f = RateLimitFilter(max_events=3, window_seconds=60)

        event = WebSocketEvent(source="test", connection_id="1", content="hi")

        # First 3 should pass
        assert f.matches(event)
        assert f.matches(event)
        assert f.matches(event)

        # 4th should be rejected
        assert not f.matches(event)

    def test_convenience_function(self) -> None:
        """Test rate_limit_filter convenience function."""
        f = rate_limit_filter(100, 60)
        assert isinstance(f, RateLimitFilter)
        assert f.max_events == 100
        assert f.window_seconds == 60


class TestDedupeFilter:
    """Tests for DedupeFilter class."""

    def test_first_event_passes(self) -> None:
        """Test first event with unique key passes."""
        f = DedupeFilter(key_func=lambda e: e.id)

        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        assert f.matches(event)

    def test_duplicate_rejected(self) -> None:
        """Test duplicate events are rejected."""
        f = DedupeFilter(key_func=lambda e: e.id)

        event = WebSocketEvent(id="same-id", source="test", connection_id="1", content="hi")

        assert f.matches(event)  # First pass
        assert not f.matches(event)  # Duplicate rejected

    def test_different_keys_pass(self) -> None:
        """Test events with different keys pass."""
        f = DedupeFilter(key_func=lambda e: e.id)

        event1 = WebSocketEvent(id="id-1", source="test", connection_id="1", content="hi")
        event2 = WebSocketEvent(id="id-2", source="test", connection_id="1", content="hi")

        assert f.matches(event1)
        assert f.matches(event2)

    def test_lru_eviction(self) -> None:
        """Test LRU eviction when max_keys exceeded."""
        f = DedupeFilter(key_func=lambda e: e.id, max_keys=3)

        # Add 4 events to trigger eviction
        for i in range(4):
            event = WebSocketEvent(id=f"id-{i}", source="test", connection_id="1", content="hi")
            assert f.matches(event)

        # First event should have been evicted
        event_first = WebSocketEvent(id="id-0", source="test", connection_id="1", content="hi")
        assert f.matches(event_first)  # Should pass as it was evicted

    def test_convenience_function(self) -> None:
        """Test dedupe_filter convenience function."""
        f = dedupe_filter(lambda e: e.id, window_seconds=300, max_keys=1000)
        assert isinstance(f, DedupeFilter)
        assert f.window_seconds == 300
        assert f.max_keys == 1000


# --- FilterContext tests ---


class TestFilterContext:
    """Tests for FilterContext dataclass."""

    def test_empty_context(self) -> None:
        """Test creating empty filter context."""
        ctx = FilterContext()
        assert ctx.events == []
        assert ctx.last_action_time is None
        assert ctx.metadata == {}

    def test_context_with_events(self) -> None:
        """Test context with events."""
        event = WebSocketEvent(source="test", connection_id="1", content="hi")
        ctx = FilterContext(events=[event])
        assert len(ctx.events) == 1
        assert ctx.events[0] is event

    def test_context_with_metadata(self) -> None:
        """Test context with metadata."""
        ctx = FilterContext(metadata={"key": "value"})
        assert ctx.metadata["key"] == "value"


# --- Backward compatibility tests ---


class TestBackwardCompatibility:
    """Tests for backward-compatible filter functions."""

    def test_event_type_filter_function(self) -> None:
        """Test event_type_filter returns callable."""
        ctx = DecisionContext()
        f = event_type_filter("ws.message", "http.request")

        ws_event = WebSocketEvent(source="test", connection_id="1", content="hi")
        http_event = HTTPEvent(source="test", method="GET", path="/")
        timer_event = TimerEvent(source="test", timer_name="tick")

        assert f(ws_event, ctx)
        assert f(http_event, ctx)
        assert not f(timer_event, ctx)

    def test_all_filters_and(self) -> None:
        """Test all_filters combines with AND logic."""
        ctx = DecisionContext()
        f = all_filters(
            event_type_filter("ws.message"),
            lambda e, c: "hello" in e.model_dump_json().lower(),
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
