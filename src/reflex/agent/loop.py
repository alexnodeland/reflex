"""Main event processing loop.

The loop subscribes to events, matches them against triggers,
and executes agents with proper error handling and concurrency control.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import logfire

from reflex.agent.triggers import get_registry
from reflex.core.context import AgentContext
from reflex.infra.locks import ScopedLocks

if TYPE_CHECKING:
    from reflex.infra.store import EventStore


async def run_loop(
    store: EventStore,
    event_types: list[str] | None = None,
    max_concurrent: int = 10,
) -> None:
    """Run the main event processing loop.

    Subscribes to events from the store, matches them against
    registered triggers, and executes the corresponding agents.

    Features:
    - Scoped locking prevents concurrent execution for same scope
    - Automatic ack/nack based on agent success/failure
    - Bounded concurrency via semaphore
    - Full observability through Logfire

    Args:
        store: The event store to subscribe to
        event_types: Optional list of event types to filter
        max_concurrent: Maximum concurrent agent executions
    """
    registry = get_registry()
    locks = ScopedLocks()
    semaphore = asyncio.Semaphore(max_concurrent)

    logfire.info(
        "Event loop starting",
        event_types=event_types,
        max_concurrent=max_concurrent,
        trigger_count=len(registry.triggers),
    )

    async def publish_event(event: Any) -> None:
        """Publish a new event to the store."""
        await store.publish(event)

    async def process_event(event: Any, token: str) -> None:
        """Process a single event through matching triggers."""
        async with semaphore:
            triggers = registry.match(event)

            if not triggers:
                logfire.debug(
                    "No triggers matched",
                    event_id=event.id,
                    event_type=event.type,
                )
                await store.ack(token)
                return

            logfire.info(
                "Processing event",
                event_id=event.id,
                event_type=event.type,
                trigger_count=len(triggers),
            )

            # Execute all matching triggers
            errors: list[str] = []
            for trigger in triggers:
                scope = trigger.get_scope(event)

                try:
                    async with locks.acquire(scope):
                        ctx = AgentContext(
                            event=event,
                            store=store,
                            publish=publish_event,
                            scope=scope,
                        )

                        with logfire.span(
                            "trigger.execute",
                            trigger=trigger.name,
                            scope=scope,
                        ):
                            await trigger.agent.run(ctx)

                except Exception as e:
                    logfire.error(
                        "Trigger execution failed",
                        trigger=trigger.name,
                        event_id=event.id,
                        error=str(e),
                    )
                    errors.append(f"{trigger.name}: {e}")

            # Ack or nack based on results
            if errors:
                await store.nack(token, "; ".join(errors))
            else:
                await store.ack(token)

    # Track background tasks to prevent garbage collection
    background_tasks: set[asyncio.Task[None]] = set()

    # Main subscription loop
    async for event, token in store.subscribe(event_types=event_types):
        # Process each event in a separate task for concurrency
        task = asyncio.create_task(process_event(event, token))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)


async def run_once(
    store: EventStore,
    event: Any,
) -> list[Exception]:
    """Process a single event synchronously.

    Useful for testing and debugging. Runs all matching triggers
    and returns any exceptions that occurred.

    Args:
        store: The event store
        event: The event to process

    Returns:
        List of exceptions that occurred during processing
    """
    registry = get_registry()
    locks = ScopedLocks()
    errors: list[Exception] = []

    async def publish_event(e: Any) -> None:
        await store.publish(e)

    triggers = registry.match(event)

    for trigger in triggers:
        scope = trigger.get_scope(event)

        try:
            async with locks.acquire(scope):
                ctx = AgentContext(
                    event=event,
                    store=store,
                    publish=publish_event,
                    scope=scope,
                )
                await trigger.agent.run(ctx)
        except Exception as e:
            errors.append(e)

    return errors
