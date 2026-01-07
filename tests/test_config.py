"""Tests for configuration module."""

import pytest


class TestSettings:
    """Tests for the Settings class."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        from reflex.config import Settings

        # Create fresh settings instance to test defaults
        settings = Settings()

        assert settings.database_pool_size == 5
        assert settings.database_pool_max_overflow == 10
        assert settings.api_port == 8000
        assert settings.api_reload is False
        assert settings.log_level == "INFO"
        assert settings.default_model == "openai:gpt-4o-mini"
        assert settings.event_max_attempts == 3
        assert settings.event_retry_base_delay == 1.0
        assert settings.event_retry_max_delay == 60.0
        assert settings.environment == "development"
        assert settings.version == "0.1.0"

    def test_environment_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variables override defaults."""
        from reflex.config import Settings

        monkeypatch.setenv("DATABASE_POOL_SIZE", "10")
        monkeypatch.setenv("API_PORT", "9000")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("ENVIRONMENT", "production")

        settings = Settings()

        assert settings.database_pool_size == 10
        assert settings.api_port == 9000
        assert settings.log_level == "DEBUG"
        assert settings.environment == "production"

    def test_optional_fields_none_by_default(self) -> None:
        """Test that optional fields are None by default."""
        from reflex.config import Settings

        settings = Settings()

        assert settings.logfire_token is None
        assert settings.openai_api_key is None

    def test_singleton_import(self) -> None:
        """Test that settings singleton is importable."""
        from reflex.config import settings

        assert settings is not None
        assert settings.version == "0.1.0"


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_database_url_format(self) -> None:
        """Test that database URL has correct format."""
        from reflex.config import Settings

        settings = Settings()
        assert settings.database_url.startswith("postgresql+asyncpg://")

    def test_numeric_constraints(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that numeric values are parsed correctly."""
        from reflex.config import Settings

        monkeypatch.setenv("EVENT_RETRY_BASE_DELAY", "2.5")
        monkeypatch.setenv("EVENT_RETRY_MAX_DELAY", "120.0")

        settings = Settings()

        assert settings.event_retry_base_delay == 2.5
        assert settings.event_retry_max_delay == 120.0
