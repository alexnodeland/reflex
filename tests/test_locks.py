"""Tests for ScopedLocks."""

import asyncio

from reflex.locks import ScopedLocks


class TestScopedLocks:
    """Tests for ScopedLocks."""

    def test_create(self) -> None:
        """Should create ScopedLocks."""
        locks = ScopedLocks()
        assert locks._locks == {}

    async def test_get_lock_async(self) -> None:
        """Should return a lock for a scope."""
        locks = ScopedLocks()
        lock = await locks("test-scope")

        assert isinstance(lock, asyncio.Lock)

    def test_get_lock_sync(self) -> None:
        """Should return a lock for a scope synchronously."""
        locks = ScopedLocks()
        lock = locks.get("test-scope")

        assert isinstance(lock, asyncio.Lock)

    async def test_same_scope_same_lock(self) -> None:
        """Same scope should return the same lock."""
        locks = ScopedLocks()

        lock1 = await locks("scope-a")
        lock2 = await locks("scope-a")

        assert lock1 is lock2

    async def test_different_scope_different_lock(self) -> None:
        """Different scopes should return different locks."""
        locks = ScopedLocks()

        lock_a = await locks("scope-a")
        lock_b = await locks("scope-b")

        assert lock_a is not lock_b

    async def test_lock_mutual_exclusion(self) -> None:
        """Lock should provide mutual exclusion."""
        locks = ScopedLocks()
        lock = await locks("test")

        execution_order: list[str] = []

        async def task(name: str, delay: float) -> None:
            async with lock:
                execution_order.append(f"{name}-start")
                await asyncio.sleep(delay)
                execution_order.append(f"{name}-end")

        # Start two tasks
        task1 = asyncio.create_task(task("A", 0.1))
        await asyncio.sleep(0.01)  # Let task1 acquire the lock first
        task2 = asyncio.create_task(task("B", 0.1))

        await asyncio.gather(task1, task2)

        # Task A should complete before Task B starts
        assert execution_order == ["A-start", "A-end", "B-start", "B-end"]

    async def test_different_scopes_concurrent(self) -> None:
        """Different scopes should allow concurrent execution."""
        locks = ScopedLocks()

        execution_order: list[str] = []

        async def task(scope: str, name: str) -> None:
            lock = await locks(scope)
            async with lock:
                execution_order.append(f"{name}-start")
                await asyncio.sleep(0.05)
                execution_order.append(f"{name}-end")

        # Start tasks with different scopes
        task1 = asyncio.create_task(task("scope-a", "A"))
        await asyncio.sleep(0.01)
        task2 = asyncio.create_task(task("scope-b", "B"))

        await asyncio.gather(task1, task2)

        # B should start before A ends (concurrent execution)
        assert execution_order.index("B-start") < execution_order.index("A-end")
