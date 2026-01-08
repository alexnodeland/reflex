"""Tests for scoped locking utilities."""

import asyncio

import pytest

from reflex.infra.locks import (
    InMemoryLockBackend,
    LockBackend,
    ScopedLocks,
    create_lock_backend,
)


class TestInMemoryLockBackend:
    """Tests for InMemoryLockBackend."""

    def test_creation_with_warning(self) -> None:
        """Test InMemoryLockBackend emits warning by default."""
        with pytest.warns(UserWarning, match="single-process"):
            backend = InMemoryLockBackend()
            assert backend is not None

    def test_creation_without_warning(self) -> None:
        """Test InMemoryLockBackend can suppress warning."""
        # Should not emit warning
        backend = InMemoryLockBackend(warn_on_init=False)
        assert backend is not None

    @pytest.mark.asyncio
    async def test_acquire_and_release(self) -> None:
        """Test basic lock acquire and release."""
        backend = InMemoryLockBackend(warn_on_init=False)

        acquired = await backend.acquire("test:scope")
        assert acquired is True
        assert await backend.is_locked("test:scope")

        await backend.release("test:scope")
        assert not await backend.is_locked("test:scope")

    @pytest.mark.asyncio
    async def test_acquire_with_timeout(self) -> None:
        """Test acquiring lock with timeout."""
        backend = InMemoryLockBackend(warn_on_init=False)

        # First acquire should succeed
        acquired = await backend.acquire("test:scope", wait_timeout=1.0)
        assert acquired is True

        # Second acquire with short timeout should fail
        async def try_acquire() -> bool:
            return await backend.acquire("test:scope", wait_timeout=0.01)

        result = await try_acquire()
        assert result is False

        # Release and try again
        await backend.release("test:scope")
        result = await backend.acquire("test:scope", wait_timeout=0.01)
        assert result is True

    @pytest.mark.asyncio
    async def test_release_unlocked_scope(self) -> None:
        """Test releasing a scope that was never locked."""
        backend = InMemoryLockBackend(warn_on_init=False)
        # Should not raise
        await backend.release("never:locked")


class TestScopedLocks:
    """Tests for ScopedLocks class."""

    def test_lock_creation_with_backend(self) -> None:
        """Test ScopedLocks with explicit backend."""
        backend = InMemoryLockBackend(warn_on_init=False)
        locks = ScopedLocks(backend)
        assert locks is not None
        assert locks.backend is backend

    @pytest.mark.asyncio
    async def test_acquire_and_release(self) -> None:
        """Test basic lock acquire and release."""
        backend = InMemoryLockBackend(warn_on_init=False)
        locks = ScopedLocks(backend)

        async with locks.acquire("user:123"):
            assert locks.is_locked("user:123")

        assert not locks.is_locked("user:123")

    @pytest.mark.asyncio
    async def test_different_scopes_independent(self) -> None:
        """Test that different scopes don't block each other."""
        backend = InMemoryLockBackend(warn_on_init=False)
        locks = ScopedLocks(backend)
        results: list[str] = []

        async def task1() -> None:
            async with locks.acquire("scope:a"):
                results.append("a:start")
                await asyncio.sleep(0.01)
                results.append("a:end")

        async def task2() -> None:
            async with locks.acquire("scope:b"):
                results.append("b:start")
                await asyncio.sleep(0.01)
                results.append("b:end")

        # Run both tasks concurrently
        await asyncio.gather(task1(), task2())

        # Both should have started before either ended (interleaved)
        assert "a:start" in results
        assert "b:start" in results
        assert "a:end" in results
        assert "b:end" in results

    @pytest.mark.asyncio
    async def test_same_scope_serialized(self) -> None:
        """Test that same scope locks are serialized."""
        backend = InMemoryLockBackend(warn_on_init=False)
        locks = ScopedLocks(backend)
        results: list[str] = []

        async def task(name: str) -> None:
            async with locks.acquire("shared:scope"):
                results.append(f"{name}:start")
                await asyncio.sleep(0.01)
                results.append(f"{name}:end")

        # Run both tasks concurrently on same scope
        await asyncio.gather(task("1"), task("2"))

        # Should be serialized: one task completes before other starts
        # Either [1:start, 1:end, 2:start, 2:end] or [2:start, 2:end, 1:start, 1:end]
        if results[0] == "1:start":
            assert results == ["1:start", "1:end", "2:start", "2:end"]
        else:
            assert results == ["2:start", "2:end", "1:start", "1:end"]

    @pytest.mark.asyncio
    async def test_is_locked_when_not_acquired(self) -> None:
        """Test is_locked returns False for unacquired scope."""
        backend = InMemoryLockBackend(warn_on_init=False)
        locks = ScopedLocks(backend)
        assert not locks.is_locked("never:acquired")

    @pytest.mark.asyncio
    async def test_is_locked_async(self) -> None:
        """Test async is_locked check."""
        backend = InMemoryLockBackend(warn_on_init=False)
        locks = ScopedLocks(backend)

        assert not await locks.is_locked_async("test:scope")

        await backend.acquire("test:scope")
        assert await locks.is_locked_async("test:scope")

        await backend.release("test:scope")
        assert not await locks.is_locked_async("test:scope")

    @pytest.mark.asyncio
    async def test_lock_reentrant_different_coroutines(self) -> None:
        """Test that locks block different coroutines on same scope."""
        backend = InMemoryLockBackend(warn_on_init=False)
        locks = ScopedLocks(backend)
        acquired = asyncio.Event()
        can_continue = asyncio.Event()

        async def holder() -> None:
            async with locks.acquire("test:scope"):
                acquired.set()
                await can_continue.wait()

        async def waiter() -> bool:
            await acquired.wait()  # Wait for holder to acquire
            # This should block until holder releases
            start = asyncio.get_event_loop().time()
            async with locks.acquire("test:scope"):
                elapsed = asyncio.get_event_loop().time() - start
                return elapsed > 0.01  # Should have waited

        # Start holder
        holder_task = asyncio.create_task(holder())
        await asyncio.sleep(0.01)  # Let holder acquire lock

        # Start waiter and let it block
        waiter_task = asyncio.create_task(waiter())
        await asyncio.sleep(0.01)

        # Release holder
        can_continue.set()

        # Waiter should now complete
        waited = await waiter_task
        await holder_task

        assert waited, "Waiter should have blocked"

    @pytest.mark.asyncio
    async def test_acquire_timeout_raises(self) -> None:
        """Test that acquire raises TimeoutError when timeout expires."""
        backend = InMemoryLockBackend(warn_on_init=False)
        locks = ScopedLocks(backend)

        # Hold the lock
        await backend.acquire("test:scope")

        # Try to acquire with timeout - should raise
        with pytest.raises(TimeoutError, match="Failed to acquire lock"):
            async with locks.acquire("test:scope", wait_timeout=0.01):
                pass


class TestCreateLockBackend:
    """Tests for create_lock_backend factory function."""

    def test_create_memory_backend(self) -> None:
        """Test creating memory backend."""
        backend = create_lock_backend("memory", warn_on_memory=False)
        assert isinstance(backend, InMemoryLockBackend)

    def test_create_memory_backend_with_warning(self) -> None:
        """Test creating memory backend with warning."""
        with pytest.warns(UserWarning, match="single-process"):
            backend = create_lock_backend("memory", warn_on_memory=True)
            assert isinstance(backend, InMemoryLockBackend)

    def test_create_postgres_backend_requires_pool(self) -> None:
        """Test that postgres backend requires pool."""
        with pytest.raises(ValueError, match="requires an asyncpg pool"):
            create_lock_backend("postgres")

    def test_invalid_backend_type(self) -> None:
        """Test that invalid backend type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown lock backend"):
            create_lock_backend("invalid")


class TestLockBackendInterface:
    """Tests to verify LockBackend interface compliance."""

    def test_inmemory_implements_interface(self) -> None:
        """Test InMemoryLockBackend implements LockBackend."""
        backend = InMemoryLockBackend(warn_on_init=False)
        assert isinstance(backend, LockBackend)
        assert hasattr(backend, "acquire")
        assert hasattr(backend, "release")
        assert hasattr(backend, "is_locked")
        assert hasattr(backend, "close")
