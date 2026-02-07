"""
Repository for Google Wallet callback nonce tracking.
Prevents duplicate callback processing.
"""

from database.connection import get_db, with_retry


class CallbackNonceRepository:
    """Repository for managing Google callback nonces."""

    @staticmethod
    @with_retry()
    def exists(nonce: str) -> bool:
        """Check if a nonce has already been processed."""
        db = get_db()
        result = db.table("google_callback_nonces").select("nonce").eq(
            "nonce", nonce
        ).limit(1).execute()
        return len(result.data) > 0

    @staticmethod
    @with_retry()
    def mark_processed(nonce: str) -> None:
        """Mark a nonce as processed."""
        db = get_db()
        db.table("google_callback_nonces").insert({
            "nonce": nonce,
        }).execute()

    @staticmethod
    @with_retry()
    def cleanup_old(days: int = 7) -> int:
        """
        Delete nonces older than specified days.
        Returns number of deleted records.

        Note: This can also be done via the cleanup_old_callback_nonces()
        SQL function defined in the migration.
        """
        db = get_db()
        # Use raw SQL via RPC for date arithmetic
        result = db.rpc("cleanup_old_callback_nonces").execute()
        return result.data if result.data else 0
