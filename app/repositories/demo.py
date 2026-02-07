"""
Demo repositories for interactive landing page demo.
Completely isolated from business repositories.
"""
import secrets
from database.connection import get_db, with_retry


class DemoSessionRepository:
    """Repository for demo session management."""

    @staticmethod
    @with_retry()
    def create() -> dict | None:
        """Create a new demo session with unique token."""
        db = get_db()
        session_token = secrets.token_urlsafe(32)
        result = db.table("demo_sessions").insert({
            "session_token": session_token,
            "status": "pending",
            "stamps": 0,
        }).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_id(session_id: str) -> dict | None:
        """Get session by ID."""
        db = get_db()
        result = db.table("demo_sessions").select("*").eq("id", session_id).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_token(session_token: str) -> dict | None:
        """Get session by token."""
        db = get_db()
        result = db.table("demo_sessions").select("*").eq(
            "session_token", session_token
        ).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def update_status(
        session_id: str,
        status: str,
        demo_customer_id: str = None,
        wallet_provider: str = None,
    ) -> dict | None:
        """Update session status and optionally link customer/wallet provider."""
        db = get_db()
        data = {"status": status}
        if demo_customer_id:
            data["demo_customer_id"] = demo_customer_id
        if wallet_provider:
            data["wallet_provider"] = wallet_provider
        result = db.table("demo_sessions").update(data).eq("id", session_id).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def add_stamp(session_id: str) -> int:
        """Add stamp to session, return new count."""
        db = get_db()
        session = db.table("demo_sessions").select("stamps").eq("id", session_id).limit(1).execute()
        if not session or not session.data:
            raise ValueError("Session not found")

        new_stamps = min(session.data[0]["stamps"] + 1, 8)
        db.table("demo_sessions").update({
            "stamps": new_stamps,
        }).eq("id", session_id).execute()
        return new_stamps

    @staticmethod
    @with_retry()
    def cleanup_expired() -> int:
        """Delete expired sessions. Returns count deleted."""
        db = get_db()
        result = db.table("demo_sessions").delete().lt("expires_at", "now()").execute()
        return len(result.data) if result and result.data else 0


class DemoCustomerRepository:
    """Repository for demo customer management."""

    @staticmethod
    @with_retry()
    def create(session_id: str) -> dict | None:
        """Create demo customer linked to session."""
        db = get_db()
        auth_token = secrets.token_hex(16)
        result = db.table("demo_customers").insert({
            "session_id": session_id,
            "auth_token": auth_token,
            "stamps": 0,
        }).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_id(customer_id: str) -> dict | None:
        """Get demo customer by ID."""
        db = get_db()
        result = db.table("demo_customers").select("*").eq("id", customer_id).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_auth_token(customer_id: str, auth_token: str) -> dict | None:
        """Verify auth token matches customer."""
        db = get_db()
        result = db.table("demo_customers").select("*").eq(
            "id", customer_id
        ).eq("auth_token", auth_token).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def add_stamp(customer_id: str) -> int:
        """Add stamp to customer, return new count."""
        db = get_db()
        customer = db.table("demo_customers").select("stamps").eq("id", customer_id).limit(1).execute()
        if not customer or not customer.data:
            raise ValueError("Customer not found")

        new_stamps = min(customer.data[0]["stamps"] + 1, 8)
        db.table("demo_customers").update({
            "stamps": new_stamps,
        }).eq("id", customer_id).execute()
        return new_stamps

    @staticmethod
    @with_retry()
    def get_session(customer_id: str) -> dict | None:
        """Get the session linked to this customer."""
        db = get_db()
        customer = db.table("demo_customers").select("session_id").eq("id", customer_id).limit(1).execute()
        if not customer or not customer.data:
            return None

        session_id = customer.data[0]["session_id"]
        return DemoSessionRepository.get_by_id(session_id)


class DemoDeviceRepository:
    """Repository for demo device registration."""

    @staticmethod
    @with_retry()
    def register(demo_customer_id: str, device_library_id: str, push_token: str):
        """Register an Apple Wallet device for push notifications."""
        db = get_db()
        db.table("demo_push_registrations").upsert({
            "demo_customer_id": demo_customer_id,
            "device_library_id": device_library_id,
            "push_token": push_token,
            "wallet_type": "apple",
        }, on_conflict="demo_customer_id,device_library_id,wallet_type").execute()

    @staticmethod
    @with_retry()
    def unregister(demo_customer_id: str, device_library_id: str):
        """Unregister a device from push notifications."""
        db = get_db()
        db.table("demo_push_registrations").delete().eq(
            "demo_customer_id", demo_customer_id
        ).eq("device_library_id", device_library_id).execute()

    @staticmethod
    @with_retry()
    def get_push_tokens(demo_customer_id: str) -> list[str]:
        """Get all push tokens for a demo customer."""
        db = get_db()
        result = db.table("demo_push_registrations").select("push_token").eq(
            "demo_customer_id", demo_customer_id
        ).execute()
        return [row["push_token"] for row in result.data]

    @staticmethod
    @with_retry()
    def get_serial_numbers_for_device(device_library_id: str) -> list[str]:
        """Get all serial numbers registered to a device."""
        db = get_db()
        result = db.table("demo_push_registrations").select("demo_customer_id").eq(
            "device_library_id", device_library_id
        ).execute()
        return [row["demo_customer_id"] for row in result.data]

    @staticmethod
    @with_retry()
    def register_google(demo_customer_id: str, google_object_id: str):
        """Register a Google Wallet save for demo."""
        db = get_db()
        db.table("demo_push_registrations").upsert({
            "demo_customer_id": demo_customer_id,
            "wallet_type": "google",
            "google_object_id": google_object_id,
        }, on_conflict="demo_customer_id,google_object_id").execute()

    @staticmethod
    @with_retry()
    def unregister_google(demo_customer_id: str, google_object_id: str):
        """Unregister a Google Wallet save for demo."""
        db = get_db()
        db.table("demo_push_registrations").delete().eq(
            "demo_customer_id", demo_customer_id
        ).eq("google_object_id", google_object_id).execute()

    @staticmethod
    @with_retry()
    def get_wallet_type(demo_customer_id: str) -> str | None:
        """Get the wallet type used by this demo customer."""
        db = get_db()
        result = db.table("demo_push_registrations").select("wallet_type").eq(
            "demo_customer_id", demo_customer_id
        ).limit(1).execute()
        return result.data[0]["wallet_type"] if result.data else None

    @staticmethod
    @with_retry()
    def has_google_wallet(demo_customer_id: str) -> bool:
        """Check if demo customer has a Google Wallet registration."""
        db = get_db()
        result = db.table("demo_push_registrations").select("id").eq(
            "demo_customer_id", demo_customer_id
        ).eq("wallet_type", "google").limit(1).execute()
        return bool(result.data)
