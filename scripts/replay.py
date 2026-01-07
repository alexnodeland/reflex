#!/usr/bin/env python
"""Event replay utility.

Usage:
    python scripts/replay.py --last 1h
    python scripts/replay.py --start 2024-01-01T00:00:00 --end 2024-01-02T00:00:00
    python scripts/replay.py --last 24h --type ws.message

This script replays historical events from the database for debugging
or reprocessing purposes.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from datetime import UTC, datetime, timedelta

# Ensure the project is in the path
sys.path.insert(0, "src")


def parse_duration(duration: str) -> timedelta:
    """Parse duration string like '1h', '30m', '7d' into timedelta."""
    match = re.match(r"(\d+)([smhd])", duration.lower())
    if not match:
        raise ValueError(f"Invalid duration format: {duration}")

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "s":
        return timedelta(seconds=value)
    elif unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    else:
        raise ValueError(f"Unknown time unit: {unit}")


async def main() -> None:
    """Run event replay."""
    parser = argparse.ArgumentParser(
        description="Replay historical events from the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/replay.py --last 1h
    python scripts/replay.py --last 24h --type ws.message
    python scripts/replay.py --start 2024-01-01T00:00:00
        """,
    )
    parser.add_argument(
        "--last",
        type=str,
        help="Replay events from last duration (e.g., 1h, 30m, 7d)",
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Start timestamp (ISO format)",
    )
    parser.add_argument(
        "--end",
        type=str,
        help="End timestamp (ISO format, defaults to now)",
    )
    parser.add_argument(
        "--type",
        type=str,
        action="append",
        dest="types",
        help="Filter by event type (can be specified multiple times)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output events as JSON lines",
    )

    args = parser.parse_args()

    # Determine time range
    now = datetime.now(UTC)
    if args.last:
        start = now - parse_duration(args.last)
        end = now
    elif args.start:
        start = datetime.fromisoformat(args.start)
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        end = datetime.fromisoformat(args.end) if args.end else now
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
    else:
        parser.error("Either --last or --start is required")
        return

    # Import after path setup
    from reflex.infra.database import SessionFactory, create_raw_pool, dispose_engine
    from reflex.infra.store import EventStore

    print(f"Replaying events from {start.isoformat()} to {end.isoformat()}", file=sys.stderr)
    if args.types:
        print(f"Filtering by types: {', '.join(args.types)}", file=sys.stderr)

    pool = await create_raw_pool()
    store = EventStore(pool=pool, session_factory=SessionFactory)

    try:
        count = 0
        async for event in store.replay(start=start, end=end, event_types=args.types):
            count += 1
            if args.json:
                print(event.model_dump_json())
            else:
                print(
                    f"[{event.timestamp.isoformat()}] {event.type} from {event.source}: {event.id}"
                )

        print(f"\nReplayed {count} events", file=sys.stderr)
    finally:
        await pool.close()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
