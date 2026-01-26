import aiosqlite
import os
from contextlib import asynccontextmanager

DATABASE_PATH = os.getenv("DATABASE_PATH", "loyalty.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    stamps INTEGER DEFAULT 0 CHECK (stamps >= 0 AND stamps <= 10),
    auth_token TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS push_registrations (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    device_library_id TEXT NOT NULL,
    push_token TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    UNIQUE(customer_id, device_library_id)
);

CREATE INDEX IF NOT EXISTS idx_push_customer ON push_registrations(customer_id);
CREATE INDEX IF NOT EXISTS idx_customer_email ON customers(email);
"""


async def init_db():
    """Initialize the database with schema."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


@asynccontextmanager
async def get_db():
    """Get a database connection."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def create_customer(customer_id: str, name: str, email: str, auth_token: str) -> dict:
    """Create a new customer."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO customers (id, name, email, auth_token) VALUES (?, ?, ?, ?)",
            (customer_id, name, email, auth_token)
        )
        await db.commit()
        return {"id": customer_id, "name": name, "email": email, "stamps": 0}


async def get_customer(customer_id: str) -> dict | None:
    """Get a customer by ID."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, email, stamps, auth_token, created_at, updated_at FROM customers WHERE id = ?",
            (customer_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None


async def get_customer_by_email(email: str) -> dict | None:
    """Get a customer by email."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, email, stamps, auth_token FROM customers WHERE email = ?",
            (email,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None


async def add_stamp(customer_id: str) -> int:
    """Add a stamp to a customer. Returns the new stamp count."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT stamps FROM customers WHERE id = ?",
            (customer_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise ValueError("Customer not found")

        current_stamps = row["stamps"]
        new_stamps = min(current_stamps + 1, 10)

        await db.execute(
            "UPDATE customers SET stamps = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_stamps, customer_id)
        )
        await db.commit()
        return new_stamps


async def register_device(registration_id: str, customer_id: str, device_library_id: str, push_token: str):
    """Register a device for push notifications."""
    async with get_db() as db:
        await db.execute(
            """INSERT INTO push_registrations (id, customer_id, device_library_id, push_token)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(customer_id, device_library_id) DO UPDATE SET push_token = ?""",
            (registration_id, customer_id, device_library_id, push_token, push_token)
        )
        await db.commit()


async def unregister_device(customer_id: str, device_library_id: str):
    """Unregister a device from push notifications."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM push_registrations WHERE customer_id = ? AND device_library_id = ?",
            (customer_id, device_library_id)
        )
        await db.commit()


async def get_push_tokens(customer_id: str) -> list[str]:
    """Get all push tokens for a customer."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT push_token FROM push_registrations WHERE customer_id = ?",
            (customer_id,)
        )
        rows = await cursor.fetchall()
        return [row["push_token"] for row in rows]


async def get_customer_by_auth_token(serial_number: str, auth_token: str) -> dict | None:
    """Verify auth token matches customer (serial_number is customer_id)."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, email, stamps, auth_token FROM customers WHERE id = ? AND auth_token = ?",
            (serial_number, auth_token)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None


async def get_all_customers() -> list[dict]:
    """Get all customers ordered by creation date."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, email, stamps, created_at, updated_at FROM customers ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
