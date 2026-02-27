"""
Initialize the database schema.
Run this once before first startup, or use alembic for migrations.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import init_db, close_db
from db.models import *  # noqa: F401,F403 — ensure all models are imported


async def main():
    print("Creating database tables...")
    await init_db()
    print("Database initialized successfully.")
    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
