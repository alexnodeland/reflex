#!/usr/bin/env python
"""Database migration script.

Usage:
    python scripts/migrate.py

This script creates all tables defined in SQLModel metadata.
Run this before starting the application for the first time,
or after adding new models.
"""

import asyncio
import sys

# Ensure the project is in the path
sys.path.insert(0, "src")


async def main() -> None:
    """Run database migrations."""
    # Import after path setup
    from reflex.infra.database import dispose_engine, init_database

    # Import models to register them with SQLModel
    from reflex.infra.store import EventRecord  # noqa: F401

    print("Running database migrations...")

    try:
        await init_database()
        print("Database migrations completed successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")
        raise
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
