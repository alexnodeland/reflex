#!/usr/bin/env python
"""Dead-letter queue management utility.

Usage:
    python scripts/dlq.py list
    python scripts/dlq.py list --limit 50
    python scripts/dlq.py retry <event_id>
    python scripts/dlq.py retry-all

This script allows inspection and management of events in the
dead-letter queue (DLQ).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

# Ensure the project is in the path
sys.path.insert(0, "src")


async def list_dlq(limit: int, json_output: bool) -> None:
    """List events in the dead-letter queue."""
    from reflex.infra.database import SessionFactory, create_raw_pool, dispose_engine
    from reflex.infra.store import EventStore

    pool = await create_raw_pool()
    store = EventStore(pool=pool, session_factory=SessionFactory)

    try:
        events = await store.dlq_list(limit=limit)

        if not events:
            print("No events in dead-letter queue")
            return

        print(f"Found {len(events)} events in DLQ:\n")

        for event in events:
            if json_output:
                print(event.model_dump_json())
            else:
                print(f"ID: {event.id}")
                print(f"  Type: {event.type}")
                print(f"  Source: {event.source}")
                print(f"  Timestamp: {event.timestamp.isoformat()}")
                print()
    finally:
        await pool.close()
        await dispose_engine()


async def retry_event(event_id: str) -> None:
    """Retry a specific DLQ event."""
    from reflex.infra.database import SessionFactory, create_raw_pool, dispose_engine
    from reflex.infra.store import EventStore

    pool = await create_raw_pool()
    store = EventStore(pool=pool, session_factory=SessionFactory)

    try:
        success = await store.dlq_retry(event_id)
        if success:
            print(f"Event {event_id} moved back to pending")
        else:
            print(f"Event {event_id} not found in DLQ")
            sys.exit(1)
    finally:
        await pool.close()
        await dispose_engine()


async def retry_all() -> None:
    """Retry all DLQ events."""
    from sqlalchemy import text

    from reflex.infra.database import SessionFactory, create_raw_pool, dispose_engine

    pool = await create_raw_pool()

    try:
        async with SessionFactory() as session:
            result = await session.execute(
                text("""
                    UPDATE events
                    SET status = 'pending', attempts = 0, error = NULL
                    WHERE status = 'dlq'
                """)
            )
            await session.commit()
            count = result.rowcount or 0
            print(f"Moved {count} events from DLQ back to pending")
    finally:
        await pool.close()
        await dispose_engine()


async def main() -> None:
    """Run DLQ management."""
    parser = argparse.ArgumentParser(
        description="Manage the dead-letter queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/dlq.py list
    python scripts/dlq.py list --limit 50 --json
    python scripts/dlq.py retry evt-123abc
    python scripts/dlq.py retry-all
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # List command
    list_parser = subparsers.add_parser("list", help="List DLQ events")
    list_parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of events to show (default: 100)",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output events as JSON lines",
    )

    # Retry command
    retry_parser = subparsers.add_parser("retry", help="Retry a specific event")
    retry_parser.add_argument("event_id", help="Event ID to retry")

    # Retry-all command
    subparsers.add_parser("retry-all", help="Retry all DLQ events")

    args = parser.parse_args()

    if args.command == "list":
        await list_dlq(args.limit, args.json)
    elif args.command == "retry":
        await retry_event(args.event_id)
    elif args.command == "retry-all":
        await retry_all()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
