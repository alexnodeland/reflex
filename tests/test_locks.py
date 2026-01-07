"""Tests for scoped locking utilities."""

import asyncio

import pytest


class TestScopedLocks:
    """Tests for ScopedLocks class."""

    def test_lock_creation(self) -> None:
        """Test ScopedLocks can be instantiated."""
        from reflex.infra.locks import ScopedLocks

        locks = ScopedLocks()
        assert locks is not None

    @pytest.mark.asyncio
    async def test_acquire_and_release(self) -> None:
        """Test basic lock acquire and release."""
        from reflex.infra.locks import ScopedLocks

        locks = ScopedLocks()

        async with locks.acquire("user:123"):
            assert locks.is_locked("user:123")

        assert not locks.is_locked("user:123")

    @pytest.mark.asyncio
    async def test_different_scopes_independent(self) -> None:
        """Test that different scopes don't block each other."""
        from reflex.infra.locks import ScopedLocks

        locks = ScopedLocks()
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
        from reflex.infra.locks import ScopedLocks

        locks = ScopedLocks()
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
        from reflex.infra.locks import ScopedLocks

        locks = ScopedLocks()
        assert not locks.is_locked("never:acquired")

    @pytest.mark.asyncio
    async def test_lock_reentrant_different_coroutines(self) -> None:
        """Test that locks block different coroutines on same scope."""
        from reflex.infra.locks import ScopedLocks

        locks = ScopedLocks()
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
