from database.connection import get_db, with_retry


class DeviceRepository:
    """
    Repository for Apple Wallet device registrations.

    Note: This repository is specifically for Apple Wallet devices.
    For unified wallet registration management (Apple + Google),
    use WalletRegistrationRepository instead.
    """

    @staticmethod
    @with_retry()
    def register(customer_id: str, device_library_id: str, push_token: str):
        """Register an Apple Wallet device for push notifications."""
        db = get_db()
        db.table("push_registrations").upsert({
            "customer_id": customer_id,
            "device_library_id": device_library_id,
            "push_token": push_token,
            "wallet_type": "apple",  # Explicitly set wallet type
        }, on_conflict="customer_id,device_library_id,wallet_type").execute()

    @staticmethod
    @with_retry()
    def unregister(customer_id: str, device_library_id: str):
        """Unregister an Apple Wallet device from push notifications."""
        db = get_db()
        db.table("push_registrations").delete().eq(
            "customer_id", customer_id
        ).eq("device_library_id", device_library_id).eq(
            "wallet_type", "apple"
        ).execute()

    @staticmethod
    @with_retry()
    def get_push_tokens(customer_id: str) -> list[str]:
        """Get all Apple push tokens for a customer."""
        db = get_db()
        result = db.table("push_registrations").select("push_token").eq(
            "customer_id", customer_id
        ).eq("wallet_type", "apple").execute()
        return [row["push_token"] for row in result.data if row.get("push_token")]

    @staticmethod
    @with_retry()
    def get_serial_numbers_for_device(device_library_id: str) -> list[str]:
        """Get all serial numbers (customer IDs) registered to an Apple device."""
        db = get_db()
        result = db.table("push_registrations").select("customer_id").eq(
            "device_library_id", device_library_id
        ).eq("wallet_type", "apple").execute()
        return [row["customer_id"] for row in result.data]

    @staticmethod
    @with_retry()
    def get_all_for_business(business_id: str) -> list[dict]:
        """Get all Apple push registrations for a business (via customers)."""
        db = get_db()
        result = db.table("push_registrations").select(
            "*, customers!inner(business_id)"
        ).eq("customers.business_id", business_id).eq(
            "wallet_type", "apple"
        ).execute()
        return result.data
