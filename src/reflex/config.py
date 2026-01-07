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

    # Agent
    openai_api_key: str | None = None
    default_model: str = "openai:gpt-4o-mini"

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


settings = Settings()
