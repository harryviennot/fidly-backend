from database.connection import get_db, with_retry


class DeviceRepository:
    """Repository for managing device/wallet registrations (Apple and Google)."""

    # ===== Apple Wallet Methods =====

    @staticmethod
    @with_retry()
    def register(customer_id: str, device_library_id: str, push_token: str):
        """Register an Apple Wallet device for push notifications."""
        db = get_db()
        db.table("push_registrations").upsert({
            "customer_id": customer_id,
            "device_library_id": device_library_id,
            "push_token": push_token,
            "wallet_type": "apple",
        }, on_conflict="customer_id,device_library_id").execute()

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
        ).eq("wallet_type", "apple").not_.is_("push_token", "null").execute()
        return [row["push_token"] for row in result.data if row.get("push_token")]

    @staticmethod
    @with_retry()
    def get_serial_numbers_for_device(device_library_id: str) -> list[str]:
        """Get all serial numbers registered to an Apple device."""
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

    # ===== Google Wallet Methods =====

    @staticmethod
    @with_retry()
    def register_google(customer_id: str, google_object_id: str):
        """
        Register a Google Wallet pass for a customer.

        Unlike Apple, Google Wallet doesn't use push tokens.
        Updates are made directly via the Google Wallet API.
        """
        db = get_db()

        # Check if registration already exists
        # Note: We can't use upsert with on_conflict because the unique index
        # is a partial index (with WHERE clause), which Supabase doesn't support
        existing = db.table("push_registrations").select("id").eq(
            "customer_id", customer_id
        ).eq("google_object_id", google_object_id).eq(
            "wallet_type", "google"
        ).limit(1).execute()

        if existing.data:
            # Already registered, nothing to do
            return

        # Insert new registration
        db.table("push_registrations").insert({
            "customer_id": customer_id,
            "wallet_type": "google",
            "google_object_id": google_object_id,
            "device_library_id": None,
            "push_token": None,
        }).execute()

    @staticmethod
    @with_retry()
    def unregister_google(customer_id: str, google_object_id: str):
        """Unregister a Google Wallet pass."""
        db = get_db()
        db.table("push_registrations").delete().eq(
            "customer_id", customer_id
        ).eq("google_object_id", google_object_id).eq(
            "wallet_type", "google"
        ).execute()

    @staticmethod
    @with_retry()
    def unregister_google_by_object_id(google_object_id: str):
        """Unregister a Google Wallet pass by object ID only."""
        db = get_db()
        db.table("push_registrations").delete().eq(
            "google_object_id", google_object_id
        ).eq("wallet_type", "google").execute()

    @staticmethod
    @with_retry()
    def get_google_registrations(customer_id: str) -> list[str]:
        """Get all Google Wallet object IDs for a customer."""
        db = get_db()
        result = db.table("push_registrations").select("google_object_id").eq(
            "customer_id", customer_id
        ).eq("wallet_type", "google").not_.is_("google_object_id", "null").execute()
        return [row["google_object_id"] for row in result.data if row.get("google_object_id")]

    @staticmethod
    @with_retry()
    def get_all_google_for_business(business_id: str) -> list[dict]:
        """Get all Google Wallet registrations for a business."""
        db = get_db()
        result = db.table("push_registrations").select(
            "*, customers!inner(business_id)"
        ).eq("customers.business_id", business_id).eq(
            "wallet_type", "google"
        ).execute()
        return result.data

    # ===== Combined Methods =====

    @staticmethod
    @with_retry()
    def get_all_registrations_for_customer(customer_id: str) -> dict:
        """
        Get all wallet registrations for a customer (both Apple and Google).

        Returns:
            Dict with 'apple' and 'google' lists
        """
        db = get_db()
        result = db.table("push_registrations").select("*").eq(
            "customer_id", customer_id
        ).execute()

        registrations = {"apple": [], "google": []}
        for row in result.data:
            wallet_type = row.get("wallet_type", "apple")
            registrations[wallet_type].append(row)

        return registrations

    @staticmethod
    @with_retry()
    def has_any_registration(customer_id: str) -> bool:
        """Check if a customer has any wallet registration (Apple or Google)."""
        db = get_db()
        result = db.table("push_registrations").select("id", count="exact").eq(
            "customer_id", customer_id
        ).limit(1).execute()
        return bool(result.count and result.count > 0)
