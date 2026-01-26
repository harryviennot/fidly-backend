from database.connection import get_db


class CustomerRepository:

    @staticmethod
    async def create(customer_id: str, name: str, email: str, auth_token: str) -> dict:
        """Create a new customer."""
        async with get_db() as db:
            await db.execute(
                "INSERT INTO customers (id, name, email, auth_token) VALUES (?, ?, ?, ?)",
                (customer_id, name, email, auth_token)
            )
            await db.commit()
            return {"id": customer_id, "name": name, "email": email, "stamps": 0}

    @staticmethod
    async def get_by_id(customer_id: str) -> dict | None:
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

    @staticmethod
    async def get_by_email(email: str) -> dict | None:
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

    @staticmethod
    async def get_by_auth_token(serial_number: str, auth_token: str) -> dict | None:
        """Verify auth token matches customer."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id, name, email, stamps, auth_token, updated_at FROM customers WHERE id = ? AND auth_token = ?",
                (serial_number, auth_token)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    async def get_all() -> list[dict]:
        """Get all customers ordered by creation date."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id, name, email, stamps, created_at, updated_at FROM customers ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
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
