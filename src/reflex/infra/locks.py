"""Scoped locking utilities for concurrency control.

This module provides in-memory scoped locking for single-process deployments.
For multi-process deployments, use Postgres advisory locks or Redis.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class ScopedLocks:
    """In-memory scoped locking.

    Prevents concurrent trigger execution for the same scope.
    Each scope gets its own lock, so different scopes don't block each other.

    Usage:
        locks = ScopedLocks()

        async with locks.acquire("user:123"):
            # Only one coroutine can be here for "user:123"
            await do_work()

    For multi-process deployments, use Postgres advisory locks:

        SELECT pg_advisory_lock(hashtext('user:123'));
        -- do work --
        SELECT pg_advisory_unlock(hashtext('user:123'));

    Or Redis:

        async with redis.lock(f"reflex:lock:{scope}"):
            await do_work()
    """

    def __init__(self) -> None:
        """Initialize the scoped locks container."""
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @asynccontextmanager
    async def acquire(self, scope: str) -> AsyncIterator[None]:
        """Acquire lock for scope.

        Args:
            scope: Scope identifier (e.g., "user:123", "workflow:abc")

        Yields:
            None when lock is acquired
        """
        async with self._locks[scope]:
            yield

    def is_locked(self, scope: str) -> bool:
        """Check if scope is currently locked.

        Args:
            scope: Scope identifier

        Returns:
            True if the scope is currently locked
        """
        return scope in self._locks and self._locks[scope].locked()
