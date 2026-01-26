import aiosqlite
from contextlib import asynccontextmanager

from app.core.config import settings
from .schema import SCHEMA


async def init_db():
    """Initialize the database with schema."""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.executescript(SCHEMA)
        await db.commit()


@asynccontextmanager
async def get_db():
    """Get a database connection."""
    db = await aiosqlite.connect(settings.database_path)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()
