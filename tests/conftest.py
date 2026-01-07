"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Configure anyio to use asyncio backend."""
    return "asyncio"
