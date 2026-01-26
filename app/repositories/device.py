from database.connection import get_db


class DeviceRepository:

    @staticmethod
    async def register(registration_id: str, customer_id: str, device_library_id: str, push_token: str):
        """Register a device for push notifications."""
        async with get_db() as db:
            await db.execute(
                """INSERT INTO push_registrations (id, customer_id, device_library_id, push_token)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(customer_id, device_library_id) DO UPDATE SET push_token = ?""",
                (registration_id, customer_id, device_library_id, push_token, push_token)
            )
            await db.commit()

    @staticmethod
    async def unregister(customer_id: str, device_library_id: str):
        """Unregister a device from push notifications."""
        async with get_db() as db:
            await db.execute(
                "DELETE FROM push_registrations WHERE customer_id = ? AND device_library_id = ?",
                (customer_id, device_library_id)
            )
            await db.commit()

    @staticmethod
    async def get_push_tokens(customer_id: str) -> list[str]:
        """Get all push tokens for a customer."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT push_token FROM push_registrations WHERE customer_id = ?",
                (customer_id,)
            )
            rows = await cursor.fetchall()
            return [row["push_token"] for row in rows]

    @staticmethod
    async def get_serial_numbers_for_device(device_library_id: str) -> list[str]:
        """Get all serial numbers registered to a device."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT customer_id FROM push_registrations WHERE device_library_id = ?",
                (device_library_id,)
            )
            rows = await cursor.fetchall()
            return [row["customer_id"] for row in rows]
