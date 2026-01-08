"""Tests for dependency injection containers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from reflex.core.deps import (
    ExecutionContext,
    NetworkContext,
    ReflexDeps,
    StorageContext,
)


class TestStorageContext:
    """Tests for StorageContext."""

    def test_creation(self, mock_store: AsyncMock, mock_db: AsyncMock) -> None:
        """Test StorageContext creation."""
        ctx = StorageContext(store=mock_store, db=mock_db)
        assert ctx.store is mock_store
        assert ctx.db is mock_db

    def test_immutable(self, mock_store: AsyncMock, mock_db: AsyncMock) -> None:
        """Test StorageContext is frozen (immutable)."""
        ctx = StorageContext(store=mock_store, db=mock_db)
        with pytest.raises(AttributeError):
            ctx.store = mock_store  # type: ignore[misc]


class TestNetworkContext:
    """Tests for NetworkContext."""

    def test_creation(self, mock_http: MagicMock) -> None:
        """Test NetworkContext creation."""
        ctx = NetworkContext(http=mock_http)
        assert ctx.http is mock_http

    def test_immutable(self, mock_http: MagicMock) -> None:
        """Test NetworkContext is frozen (immutable)."""
        ctx = NetworkContext(http=mock_http)
        with pytest.raises(AttributeError):
            ctx.http = mock_http  # type: ignore[misc]


class TestExecutionContext:
    """Tests for ExecutionContext."""

    def test_creation_minimal(self) -> None:
        """Test ExecutionContext creation with minimal args."""
        ctx = ExecutionContext(scope="test")
        assert ctx.scope == "test"
        assert ctx.trace_id is None
        assert ctx.correlation_id is None

    def test_creation_full(self) -> None:
        """Test ExecutionContext creation with all args."""
        ctx = ExecutionContext(
            scope="test",
            trace_id="trace-123",
            correlation_id="corr-456",
        )
        assert ctx.scope == "test"
        assert ctx.trace_id == "trace-123"
        assert ctx.correlation_id == "corr-456"

    def test_immutable(self) -> None:
        """Test ExecutionContext is frozen (immutable)."""
        ctx = ExecutionContext(scope="test")
        with pytest.raises(AttributeError):
            ctx.scope = "other"  # type: ignore[misc]


class TestReflexDeps:
    """Tests for ReflexDeps."""

    def test_creation(
        self,
        mock_store: AsyncMock,
        mock_http: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Test ReflexDeps creation."""
        deps = ReflexDeps(
            store=mock_store,
            http=mock_http,
            db=mock_db,
            scope="test",
        )
        assert deps.store is mock_store
        assert deps.http is mock_http
        assert deps.db is mock_db
        assert deps.scope == "test"

    def test_creation_with_tracing(
        self,
        mock_store: AsyncMock,
        mock_http: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Test ReflexDeps creation with tracing info."""
        deps = ReflexDeps(
            store=mock_store,
            http=mock_http,
            db=mock_db,
            scope="test",
            trace_id="trace-123",
            correlation_id="corr-456",
        )
        assert deps.trace_id == "trace-123"
        assert deps.correlation_id == "corr-456"

    def test_storage_property(
        self,
        mock_store: AsyncMock,
        mock_http: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Test storage property returns StorageContext."""
        deps = ReflexDeps(
            store=mock_store,
            http=mock_http,
            db=mock_db,
            scope="test",
        )
        storage = deps.storage
        assert isinstance(storage, StorageContext)
        assert storage.store is mock_store
        assert storage.db is mock_db

    def test_network_property(
        self,
        mock_store: AsyncMock,
        mock_http: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Test network property returns NetworkContext."""
        deps = ReflexDeps(
            store=mock_store,
            http=mock_http,
            db=mock_db,
            scope="test",
        )
        network = deps.network
        assert isinstance(network, NetworkContext)
        assert network.http is mock_http

    def test_execution_property(
        self,
        mock_store: AsyncMock,
        mock_http: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Test execution property returns ExecutionContext."""
        deps = ReflexDeps(
            store=mock_store,
            http=mock_http,
            db=mock_db,
            scope="test",
            trace_id="trace-123",
            correlation_id="corr-456",
        )
        execution = deps.execution
        assert isinstance(execution, ExecutionContext)
        assert execution.scope == "test"
        assert execution.trace_id == "trace-123"
        assert execution.correlation_id == "corr-456"

    def test_from_contexts(
        self,
        mock_store: AsyncMock,
        mock_http: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Test creating ReflexDeps from context objects."""
        storage = StorageContext(store=mock_store, db=mock_db)
        network = NetworkContext(http=mock_http)
        execution = ExecutionContext(
            scope="test",
            trace_id="trace-123",
            correlation_id="corr-456",
        )

        deps = ReflexDeps.from_contexts(storage, network, execution)

        assert deps.store is mock_store
        assert deps.http is mock_http
        assert deps.db is mock_db
        assert deps.scope == "test"
        assert deps.trace_id == "trace-123"
        assert deps.correlation_id == "corr-456"

    def test_backward_compatibility(
        self,
        mock_store: AsyncMock,
        mock_http: MagicMock,
        mock_db: AsyncMock,
    ) -> None:
        """Test backward compatibility with existing code patterns."""
        # This simulates existing usage patterns
        deps = ReflexDeps(
            store=mock_store,
            http=mock_http,
            db=mock_db,
            scope="api:/events",
        )

        # Existing code should still work
        assert deps.store.publish is not None
        assert deps.http is not None
        assert deps.db is not None
        assert deps.scope == "api:/events"
