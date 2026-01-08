"""Application configuration with environment variable loading."""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be overridden via environment variables or a .env file.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql+asyncpg://reflex:reflex@localhost:5432/reflex"
    database_pool_size: int = 5
    database_pool_max_overflow: int = 10

    # API
    api_host: str = "0.0.0.0"  # noqa: S104 - Intentional for Docker container binding
    api_port: int = 8000
    api_reload: bool = False

    # Rate limiting
    rate_limit_requests: int = 100  # requests per window
    rate_limit_window: int = 60  # window in seconds

    # Locking
    # Use "memory" for single-process, "postgres" for distributed deployments
    lock_backend: Literal["memory", "postgres"] = "memory"

    # Observability
    logfire_token: str | None = None
    log_level: str = "INFO"

    # AI Model Configuration
    # Default model uses PydanticAI format: "provider:model-name"
    # Examples:
    #   - anthropic:claude-sonnet-4-5-20250514 (default)
    #   - openai:gpt-4o
    #   - google-gla:gemini-2.0-flash
    #   - groq:llama-3.3-70b-versatile
    default_model: str = "anthropic:claude-sonnet-4-5-20250514"

    # Provider API Keys - set the key for your chosen provider
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    groq_api_key: str | None = None

    # Event processing
    event_max_attempts: int = 3
    event_retry_base_delay: float = 1.0
    event_retry_max_delay: float = 60.0

    # App
    environment: str = "development"
    version: str = "0.1.0"

    @field_validator("database_pool_size")
    @classmethod
    def validate_pool_size(cls, v: int) -> int:
        """Validate database pool size is within reasonable bounds."""
        if v < 1:
            msg = "database_pool_size must be at least 1"
            raise ValueError(msg)
        if v > 100:
            msg = "database_pool_size should not exceed 100 (check your DB limits)"
            raise ValueError(msg)
        return v

    @field_validator("database_pool_max_overflow")
    @classmethod
    def validate_pool_overflow(cls, v: int) -> int:
        """Validate pool overflow is non-negative."""
        if v < 0:
            msg = "database_pool_max_overflow cannot be negative"
            raise ValueError(msg)
        if v > 50:
            msg = "database_pool_max_overflow should not exceed 50"
            raise ValueError(msg)
        return v

    @field_validator("event_retry_base_delay")
    @classmethod
    def validate_retry_base_delay(cls, v: float) -> float:
        """Validate retry base delay is positive."""
        if v <= 0:
            msg = "event_retry_base_delay must be positive"
            raise ValueError(msg)
        return v

    @field_validator("event_retry_max_delay")
    @classmethod
    def validate_retry_max_delay(cls, v: float) -> float:
        """Validate retry max delay is reasonable."""
        if v <= 0:
            msg = "event_retry_max_delay must be positive"
            raise ValueError(msg)
        if v > 3600:
            msg = "event_retry_max_delay should not exceed 3600 seconds (1 hour)"
            raise ValueError(msg)
        return v


# Default settings instance (can be overridden for testing)
_default_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the current settings instance.

    Returns the configured settings instance, creating a default one if needed.
    This function should be used instead of the global `settings` instance
    for better testability.

    Returns:
        The current Settings instance
    """
    global _default_settings
    if _default_settings is None:
        _default_settings = Settings()
    return _default_settings


def configure_settings(settings: Settings | None) -> None:
    """Configure the settings instance.

    Use this function to inject custom settings, particularly useful for testing.
    Pass None to reset to default behavior.

    Args:
        settings: Custom Settings instance, or None to reset

    Example:
        # In tests
        test_settings = Settings(environment="test", database_url="...")
        configure_settings(test_settings)
        try:
            # ... run tests
        finally:
            configure_settings(None)  # Reset
    """
    global _default_settings
    _default_settings = settings


# Backward compatibility: Keep the global singleton
# New code should use get_settings() instead
settings = Settings()
