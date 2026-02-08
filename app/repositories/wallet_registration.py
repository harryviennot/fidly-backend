"""
Repository for unified wallet registrations (Apple and Google Wallet).
Uses the push_registrations table with wallet_type discrimination.
"""

from database.connection import get_db, with_retry


class WalletRegistrationRepository:
    """Repository for managing wallet registrations across platforms."""

    @staticmethod
    @with_retry()
    def get_by_customer(customer_id: str) -> list[dict]:
        """Get all wallet registrations for a customer (both Apple and Google)."""
        db = get_db()
        result = db.table("push_registrations").select("*").eq(
            "customer_id", customer_id
        ).execute()
        return result.data

    @staticmethod
    @with_retry()
    def get_apple_registrations(customer_id: str) -> list[dict]:
        """Get all Apple Wallet registrations for a customer."""
        db = get_db()
        result = db.table("push_registrations").select("*").eq(
            "customer_id", customer_id
        ).eq("wallet_type", "apple").execute()
        return result.data

    @staticmethod
    @with_retry()
    def get_apple_tokens(customer_id: str) -> list[str]:
        """Get Apple push tokens for a customer."""
        db = get_db()
        result = db.table("push_registrations").select("push_token").eq(
            "customer_id", customer_id
        ).eq("wallet_type", "apple").execute()
        return [r["push_token"] for r in result.data if r.get("push_token")]

    @staticmethod
    @with_retry()
    def get_google_registrations(customer_id: str) -> list[dict]:
        """Get Google Wallet registrations for a customer."""
        db = get_db()
        result = db.table("push_registrations").select("*").eq(
            "customer_id", customer_id
        ).eq("wallet_type", "google").execute()
        return result.data

    @staticmethod
    @with_retry()
    def has_google_wallet(customer_id: str) -> bool:
        """Check if customer has any Google Wallet registrations."""
        db = get_db()
        result = db.table("push_registrations").select("id").eq(
            "customer_id", customer_id
        ).eq("wallet_type", "google").limit(1).execute()
        return len(result.data) > 0

    @staticmethod
    @with_retry()
    def has_apple_wallet(customer_id: str) -> bool:
        """Check if customer has any Apple Wallet registrations."""
        db = get_db()
        result = db.table("push_registrations").select("id").eq(
            "customer_id", customer_id
        ).eq("wallet_type", "apple").limit(1).execute()
        return len(result.data) > 0

    @staticmethod
    @with_retry()
    def register_apple(
        customer_id: str,
        device_library_id: str,
        push_token: str
    ) -> None:
        """Register an Apple Wallet device."""
        db = get_db()
        db.table("push_registrations").upsert({
            "customer_id": customer_id,
            "wallet_type": "apple",
            "device_library_id": device_library_id,
            "push_token": push_token,
        }, on_conflict="customer_id,device_library_id").execute()

    @staticmethod
    @with_retry()
    def unregister_apple(customer_id: str, device_library_id: str) -> None:
        """Unregister an Apple Wallet device."""
        db = get_db()
        db.table("push_registrations").delete().eq(
            "customer_id", customer_id
        ).eq("device_library_id", device_library_id).execute()

    @staticmethod
    @with_retry()
    def register_google(customer_id: str, google_object_id: str) -> None:
        """Register a Google Wallet save (from callback)."""
        db = get_db()
        # Check if registration already exists
        existing = db.table("push_registrations").select("id").eq(
            "customer_id", customer_id
        ).eq("wallet_type", "google").eq(
            "google_object_id", google_object_id
        ).limit(1).execute()

        if existing.data:
            return  # Already registered

        db.table("push_registrations").insert({
            "customer_id": customer_id,
            "wallet_type": "google",
            "google_object_id": google_object_id,
        }).execute()

    @staticmethod
    @with_retry()
    def unregister_google(customer_id: str, google_object_id: str) -> None:
        """Unregister a Google Wallet deletion (from callback)."""
        db = get_db()
        db.table("push_registrations").delete().eq(
            "customer_id", customer_id
        ).eq("wallet_type", "google").eq(
            "google_object_id", google_object_id
        ).execute()

    @staticmethod
    @with_retry()
    def get_all_apple_for_business(business_id: str) -> list[dict]:
        """Get all Apple Wallet registrations for a business (via customers)."""
        db = get_db()
        result = db.table("push_registrations").select(
            "*, customers!inner(business_id)"
        ).eq("customers.business_id", business_id).eq(
            "wallet_type", "apple"
        ).execute()
        return result.data

    @staticmethod
    @with_retry()
    def get_all_google_for_business(business_id: str) -> list[dict]:
        """Get all Google Wallet registrations for a business (via customers)."""
        db = get_db()
        result = db.table("push_registrations").select(
            "*, customers!inner(business_id)"
        ).eq("customers.business_id", business_id).eq(
            "wallet_type", "google"
        ).execute()
        return result.data
