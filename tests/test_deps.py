"""Tests for ReflexDeps."""

from unittest.mock import Mock

import httpx

from reflex.deps import ReflexDeps


class TestReflexDeps:
    """Tests for ReflexDeps dataclass."""

    def test_create(self) -> None:
        """Should create ReflexDeps."""
        mock_store = Mock()
        mock_http = Mock(spec=httpx.AsyncClient)
        mock_db = Mock()

        deps = ReflexDeps(
            event_store=mock_store,
            http=mock_http,
            db=mock_db,
            scope="test-scope",
        )

        assert deps.event_store is mock_store
        assert deps.http is mock_http
        assert deps.db is mock_db
        assert deps.scope == "test-scope"

    def test_db_optional(self) -> None:
        """Should allow None for db."""
        deps = ReflexDeps(
            event_store=Mock(),
            http=Mock(spec=httpx.AsyncClient),
            db=None,
            scope="test",
        )

        assert deps.db is None

    def test_is_dataclass(self) -> None:
        """Should be a dataclass."""
        from dataclasses import is_dataclass

        assert is_dataclass(ReflexDeps)
