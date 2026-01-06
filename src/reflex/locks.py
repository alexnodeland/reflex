"""Scoped locking to prevent concurrent actions for the same scope."""

import asyncio
from collections import defaultdict


class ScopedLocks:
    """Simple in-memory scoped locking."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def __call__(self, scope: str) -> asyncio.Lock:
        """Get the lock for a scope."""
        return self._locks[scope]

    def get(self, scope: str) -> asyncio.Lock:
        """Get the lock for a scope (sync version)."""
        return self._locks[scope]
