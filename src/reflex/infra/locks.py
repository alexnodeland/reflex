"""Scoped locking utilities for concurrency control.

This module provides pluggable lock backends for preventing concurrent
execution of triggers with the same scope.

Available backends:
- InMemoryLockBackend: Single-process only (default, with warning)
- PostgresLockBackend: Distributed locks using PostgreSQL advisory locks

For multi-process deployments (e.g., Kubernetes), use PostgresLockBackend.
"""

from __future__ import annotations

import asyncio
import logging
import warnings
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import asyncpg

logger = logging.getLogger(__name__)


class LockBackend(ABC):
    """Abstract base class for lock backends.

    Implementations must provide acquire, release, and is_locked methods.
    All lock backends should be safe for concurrent use within their scope
    (single-process for InMemory, distributed for Postgres/Redis).
    """

    @abstractmethod
    async def acquire(self, scope: str, wait_timeout: float | None = None) -> bool:
        """Acquire lock for scope.

        Args:
            scope: Scope identifier (e.g., "user:123", "workflow:abc")
            wait_timeout: Optional timeout in seconds. If None, wait indefinitely.

        Returns:
            True if lock was acquired, False if timeout expired
        """
        ...

    @abstractmethod
    async def release(self, scope: str) -> None:
        """Release lock for scope.

        Args:
            scope: Scope identifier
        """
        ...

    @abstractmethod
    async def is_locked(self, scope: str) -> bool:
        """Check if scope is currently locked.

        Args:
            scope: Scope identifier

        Returns:
            True if the scope is currently locked
        """
        ...

    async def close(self) -> None:  # noqa: B027
        """Clean up resources. Override if needed."""


class InMemoryLockBackend(LockBackend):
    """In-memory lock backend for single-process deployments.

    WARNING: These locks do NOT work across multiple processes or containers.
    If you deploy multiple replicas (e.g., in Kubernetes), you will get
    race conditions and duplicate processing.

    For distributed deployments, use PostgresLockBackend instead.

    Args:
        warn_on_init: If True (default), emit a warning about single-process limitation
    """

    def __init__(self, *, warn_on_init: bool = True) -> None:
        """Initialize the in-memory lock backend.

        Args:
            warn_on_init: Whether to emit a warning about limitations
        """
        if warn_on_init:
            warnings.warn(
                "InMemoryLockBackend only works for single-process deployments. "
                "For Kubernetes or multi-replica deployments, set LOCK_BACKEND=postgres "
                "to use PostgreSQL advisory locks instead.",
                UserWarning,
                stacklevel=2,
            )
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, scope: str, wait_timeout: float | None = None) -> bool:
        """Acquire lock for scope.

        Args:
            scope: Scope identifier
            wait_timeout: Optional timeout in seconds

        Returns:
            True if lock was acquired, False if timeout expired
        """
        lock = self._locks[scope]
        if wait_timeout is None:
            await lock.acquire()
            return True
        try:
            await asyncio.wait_for(lock.acquire(), timeout=wait_timeout)
            return True
        except TimeoutError:
            return False

    async def release(self, scope: str) -> None:
        """Release lock for scope."""
        if scope in self._locks:
            lock = self._locks[scope]
            if lock.locked():
                lock.release()

    async def is_locked(self, scope: str) -> bool:
        """Check if scope is currently locked."""
        return self.is_locked_sync(scope)

    def is_locked_sync(self, scope: str) -> bool:
        """Synchronous check if scope is currently locked."""
        return scope in self._locks and self._locks[scope].locked()


class PostgresLockBackend(LockBackend):
    """Distributed lock backend using PostgreSQL advisory locks.

    Uses pg_advisory_lock/pg_advisory_unlock for distributed locking.
    Safe for multi-process and multi-container deployments.

    Advisory locks are:
    - Session-scoped (automatically released on disconnect)
    - Reentrant (same session can acquire same lock multiple times)
    - Fast (no table writes, just memory)

    Args:
        pool: asyncpg connection pool
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        """Initialize the Postgres lock backend.

        Args:
            pool: asyncpg connection pool for lock operations
        """
        self._pool = pool
        # Track which locks we hold to handle release correctly
        self._held_locks: set[int] = set()

    def _scope_to_lock_id(self, scope: str) -> int:
        """Convert scope string to PostgreSQL advisory lock ID.

        Uses hash to convert arbitrary strings to 64-bit integers.
        Collisions are possible but extremely unlikely for reasonable scope names.

        Args:
            scope: Scope identifier string

        Returns:
            64-bit integer lock ID
        """
        # Use Python's hash and mask to 63 bits (PostgreSQL bigint is signed)
        return hash(scope) & 0x7FFFFFFFFFFFFFFF

    async def acquire(self, scope: str, wait_timeout: float | None = None) -> bool:
        """Acquire distributed lock for scope.

        Args:
            scope: Scope identifier
            wait_timeout: Optional timeout in seconds. Uses pg_try_advisory_lock if set.

        Returns:
            True if lock was acquired, False if timeout expired or lock unavailable
        """
        lock_id = self._scope_to_lock_id(scope)

        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            if wait_timeout is not None:
                # Try to acquire without blocking
                result = cast(
                    "bool", await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_id)
                )
                if result:
                    self._held_locks.add(lock_id)
                    logger.debug("Acquired advisory lock: scope=%s, lock_id=%d", scope, lock_id)
                return result
            else:
                # Block until lock is available
                await conn.execute("SELECT pg_advisory_lock($1)", lock_id)
                self._held_locks.add(lock_id)
                logger.debug("Acquired advisory lock: scope=%s, lock_id=%d", scope, lock_id)
                return True

    async def release(self, scope: str) -> None:
        """Release distributed lock for scope.

        Args:
            scope: Scope identifier
        """
        lock_id = self._scope_to_lock_id(scope)

        if lock_id not in self._held_locks:
            logger.warning("Attempting to release lock not held: scope=%s", scope)
            return

        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            await conn.execute("SELECT pg_advisory_unlock($1)", lock_id)
            self._held_locks.discard(lock_id)
            logger.debug("Released advisory lock: scope=%s, lock_id=%d", scope, lock_id)

    async def is_locked(self, scope: str) -> bool:
        """Check if scope is currently locked by any session.

        Note: This checks if ANY session holds the lock, not just this instance.

        Args:
            scope: Scope identifier

        Returns:
            True if the scope is currently locked
        """
        lock_id = self._scope_to_lock_id(scope)

        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            # Check pg_locks for advisory locks
            result = cast(
                "bool",
                await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM pg_locks
                        WHERE locktype = 'advisory'
                        AND objid = $1
                        AND granted = true
                    )
                    """,
                    lock_id,
                ),
            )
            return result

    async def close(self) -> None:
        """Release all held locks on close."""
        if self._held_locks:
            async with self._pool.acquire() as conn:  # type: ignore[union-attr]
                for lock_id in list(self._held_locks):
                    await conn.execute("SELECT pg_advisory_unlock($1)", lock_id)
            self._held_locks.clear()


class ScopedLocks:
    """High-level scoped lock manager.

    Provides a context manager interface for acquiring and releasing locks.
    Works with any LockBackend implementation.

    Usage:
        # With in-memory backend (single process)
        backend = InMemoryLockBackend(warn_on_init=False)
        locks = ScopedLocks(backend)

        # With postgres backend (distributed)
        backend = PostgresLockBackend(pool)
        locks = ScopedLocks(backend)

        async with locks.acquire("user:123"):
            # Only one coroutine/process can be here for "user:123"
            await do_work()
    """

    def __init__(self, backend: LockBackend | None = None) -> None:
        """Initialize scoped locks with a backend.

        Args:
            backend: Lock backend implementation. If None, creates InMemoryLockBackend.
        """
        if backend is None:
            # Default to in-memory for backward compatibility
            backend = InMemoryLockBackend(warn_on_init=True)
        self._backend = backend

    @asynccontextmanager
    async def acquire(self, scope: str, wait_timeout: float | None = None) -> AsyncIterator[None]:
        """Acquire lock for scope as context manager.

        Args:
            scope: Scope identifier
            wait_timeout: Optional timeout in seconds

        Yields:
            None when lock is acquired

        Raises:
            TimeoutError: If timeout expires before lock is acquired
        """
        acquired = await self._backend.acquire(scope, wait_timeout)
        if not acquired:
            raise TimeoutError(f"Failed to acquire lock for scope: {scope}")
        try:
            yield
        finally:
            await self._backend.release(scope)

    def is_locked(self, scope: str) -> bool:
        """Check if scope is currently locked (sync, for InMemory only).

        Note: For async backends like Postgres, use is_locked_async instead.

        Args:
            scope: Scope identifier

        Returns:
            True if the scope is currently locked
        """
        if isinstance(self._backend, InMemoryLockBackend):
            return self._backend.is_locked_sync(scope)
        # For other backends, return False (they need async check)
        return False

    async def is_locked_async(self, scope: str) -> bool:
        """Async check if scope is currently locked.

        Args:
            scope: Scope identifier

        Returns:
            True if the scope is currently locked
        """
        return await self._backend.is_locked(scope)

    @property
    def backend(self) -> LockBackend:
        """Get the underlying lock backend."""
        return self._backend


def create_lock_backend(
    backend_type: str,
    pool: asyncpg.Pool | None = None,
    *,
    warn_on_memory: bool = True,
) -> LockBackend:
    """Factory function to create lock backends.

    Args:
        backend_type: Either "memory" or "postgres"
        pool: asyncpg pool (required for postgres backend)
        warn_on_memory: Whether to warn when using memory backend

    Returns:
        Configured lock backend

    Raises:
        ValueError: If backend_type is invalid or postgres backend requested without pool
    """
    if backend_type == "memory":
        return InMemoryLockBackend(warn_on_init=warn_on_memory)
    elif backend_type == "postgres":
        if pool is None:
            raise ValueError("PostgresLockBackend requires an asyncpg pool")
        return PostgresLockBackend(pool)
    else:
        raise ValueError(f"Unknown lock backend: {backend_type}. Use 'memory' or 'postgres'.")
