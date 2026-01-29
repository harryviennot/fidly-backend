from database.connection import get_db


class DeviceRepository:

    @staticmethod
    def register(customer_id: str, device_library_id: str, push_token: str):
        """Register a device for push notifications."""
        db = get_db()
        db.table("push_registrations").upsert({
            "customer_id": customer_id,
            "device_library_id": device_library_id,
            "push_token": push_token,
        }, on_conflict="customer_id,device_library_id").execute()

    @staticmethod
    def unregister(customer_id: str, device_library_id: str):
        """Unregister a device from push notifications."""
        db = get_db()
        db.table("push_registrations").delete().eq(
            "customer_id", customer_id
        ).eq("device_library_id", device_library_id).execute()

    @staticmethod
    def get_push_tokens(customer_id: str) -> list[str]:
        """Get all push tokens for a customer."""
        db = get_db()
        result = db.table("push_registrations").select("push_token").eq(
            "customer_id", customer_id
        ).execute()
        return [row["push_token"] for row in result.data]

    @staticmethod
    def get_serial_numbers_for_device(device_library_id: str) -> list[str]:
        """Get all serial numbers registered to a device."""
        db = get_db()
        result = db.table("push_registrations").select("customer_id").eq(
            "device_library_id", device_library_id
        ).execute()
        return [row["customer_id"] for row in result.data]

    @staticmethod
    def get_all_for_business(business_id: str) -> list[dict]:
        """Get all push registrations for a business (via customers)."""
        db = get_db()
        result = db.table("push_registrations").select(
            "*, customers!inner(business_id)"
        ).eq("customers.business_id", business_id).execute()
        return result.data
