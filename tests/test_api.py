"""Tests for API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reflex.api.routes import events, health

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def mock_store() -> AsyncMock:
    """Create a mock EventStore."""
    store = AsyncMock()
    store.publish = AsyncMock()
    store.dlq_list = AsyncMock(return_value=[])
    store.dlq_retry = AsyncMock(return_value=True)
    return store


@pytest.fixture
def mock_session_factory() -> MagicMock:
    """Create a mock session factory."""
    factory = MagicMock()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=1)))
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=None)
    return factory


@pytest.fixture
def app(mock_store: AsyncMock, mock_session_factory: MagicMock) -> FastAPI:
    """Create a test FastAPI app with mocked dependencies."""
    app = FastAPI()
    app.include_router(health.router)
    app.include_router(events.router)

    # Set up app state with mocked dependencies
    app.state.store = mock_store
    app.state.session_factory = mock_session_factory

    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Create a test client."""
    with TestClient(app) as client:
        yield client


class TestHealthRoutes:
    """Tests for health check endpoints."""

    def test_health_returns_ok(self, client: TestClient) -> None:
        """Test /health returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_returns_healthy_status(self, client: TestClient) -> None:
        """Test /health returns healthy status."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_ready_returns_ok_when_db_connected(self, client: TestClient) -> None:
        """Test /ready returns 200 when database is connected."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"

    def test_ready_returns_503_when_db_unavailable(
        self, app: FastAPI, mock_session_factory: MagicMock
    ) -> None:
        """Test /ready returns 503 when database is unavailable."""
        # Make the session execute raise an exception
        mock_session_factory.return_value.__aenter__.return_value.execute = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        with TestClient(app) as client:
            response = client.get("/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"
            assert data["database"] == "disconnected"


class TestEventRoutes:
    """Tests for event endpoints."""

    def test_publish_event_success(self, client: TestClient, mock_store: AsyncMock) -> None:
        """Test POST /events publishes an event."""
        event_data = {
            "type": "ws.message",
            "source": "test-client",
            "connection_id": "conn-123",
            "content": "Hello, World!",
        }

        response = client.post("/events", json=event_data)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "published"
        assert "id" in data

        # Verify store.publish was called
        mock_store.publish.assert_called_once()

    def test_publish_event_invalid_type(self, client: TestClient) -> None:
        """Test POST /events rejects invalid event types."""
        event_data = {
            "type": "invalid_type",
            "source": "test",
        }

        response = client.post("/events", json=event_data)
        assert response.status_code == 422

    def test_publish_event_missing_fields(self, client: TestClient) -> None:
        """Test POST /events rejects events with missing fields."""
        event_data = {
            "type": "websocket",
            # Missing required fields
        }

        response = client.post("/events", json=event_data)
        assert response.status_code == 422

    def test_list_dlq_empty(self, client: TestClient) -> None:
        """Test GET /events/dlq returns empty list."""
        response = client.get("/events/dlq")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["events"] == []

    def test_list_dlq_with_events(self, client: TestClient, mock_store: AsyncMock) -> None:
        """Test GET /events/dlq returns events."""
        # Create a mock event
        mock_event = MagicMock()
        mock_event.model_dump.return_value = {
            "id": "evt-123",
            "type": "websocket",
            "source": "test",
        }
        mock_store.dlq_list.return_value = [mock_event]

        response = client.get("/events/dlq")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["events"]) == 1

    def test_list_dlq_with_limit(self, client: TestClient, mock_store: AsyncMock) -> None:
        """Test GET /events/dlq respects limit parameter."""
        response = client.get("/events/dlq?limit=50")
        assert response.status_code == 200
        mock_store.dlq_list.assert_called_once_with(limit=50)

    def test_retry_dlq_event_success(self, client: TestClient, mock_store: AsyncMock) -> None:
        """Test POST /events/dlq/{id}/retry succeeds."""
        response = client.post("/events/dlq/evt-123/retry")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["event_id"] == "evt-123"

        mock_store.dlq_retry.assert_called_once_with("evt-123")

    def test_retry_dlq_event_not_found(self, client: TestClient, mock_store: AsyncMock) -> None:
        """Test POST /events/dlq/{id}/retry returns 404 for unknown event."""
        mock_store.dlq_retry.return_value = False

        response = client.post("/events/dlq/unknown-id/retry")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


class TestCreateApp:
    """Tests for FastAPI app creation."""

    def test_create_app_returns_fastapi(self) -> None:
        """Test create_app returns a FastAPI instance."""
        from reflex.api.app import create_app

        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_has_title(self) -> None:
        """Test app has correct title."""
        from reflex.api.app import create_app

        app = create_app()
        assert app.title == "Reflex"

    def test_app_has_routers(self) -> None:
        """Test app has registered routers."""
        from reflex.api.app import create_app

        app = create_app()
        routes = [getattr(route, "path", "") for route in app.routes]

        assert "/health" in routes
        assert "/ready" in routes
        assert "/events" in routes
        assert "/events/dlq" in routes


class TestDependencies:
    """Tests for API dependency functions."""

    def test_get_store_returns_store(self, app: FastAPI) -> None:
        """Test get_store returns store from app state."""
        from reflex.api.deps import get_store

        request = MagicMock()
        request.app = app

        store = get_store(request)
        assert store is app.state.store

    def test_get_http_returns_client(self) -> None:
        """Test get_http returns HTTP client from app state."""
        from reflex.api.deps import get_http

        mock_http = MagicMock()
        mock_app = MagicMock()
        mock_app.state.http = mock_http

        request = MagicMock()
        request.app = mock_app

        http = get_http(request)
        assert http is mock_http

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self, app: FastAPI) -> None:
        """Test get_db yields a session."""
        from reflex.api.deps import get_db

        request = MagicMock()
        request.app = app

        async for session in get_db(request):
            assert session is not None
            break  # Just verify we get a session

    @pytest.mark.asyncio
    async def test_get_deps_returns_reflex_deps(self, app: FastAPI) -> None:
        """Test get_deps returns ReflexDeps instance."""
        from reflex.api.deps import get_deps
        from reflex.core.deps import ReflexDeps

        mock_http = MagicMock()
        app.state.http = mock_http

        request = MagicMock()
        request.app = app
        request.url.path = "/test"

        # Mock the dependencies
        store = app.state.store
        session = AsyncMock()

        deps = await get_deps(request, store, mock_http, session)
        assert isinstance(deps, ReflexDeps)
        assert deps.store is store
        assert deps.http is mock_http
        assert deps.db is session
        assert "api:/test" in deps.scope
