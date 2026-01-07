"""Tests for event filters."""

from reflex.agent.filters import (
    AndFilter,
    NotFilter,
    OrFilter,
    SourceFilter,
    TypeFilter,
    all_of,
    any_of,
    not_matching,
    source_filter,
    type_filter,
)
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
