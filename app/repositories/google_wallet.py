"""Repository for Google Wallet class and notification management."""

from database.connection import get_db, with_retry
from datetime import datetime, timedelta


class GoogleWalletRepository:
    """Database operations for Google Wallet classes."""

    @staticmethod
    @with_retry()
    def upsert_class(
        business_id: str,
        card_design_id: str | None,
        class_id: str,
        class_data: dict
    ) -> dict | None:
        """
        Create or update a Google Wallet class record.

        Args:
            business_id: The business UUID
            card_design_id: The associated card design ID
            class_id: Google Wallet class ID (issuer_id.business_id)
            class_data: Class configuration sent to Google

        Returns:
            The created/updated record
        """
        db = get_db()
        result = db.table("google_wallet_classes").upsert(
            {
                "business_id": business_id,
                "card_design_id": card_design_id,
                "class_id": class_id,
                "class_data": class_data,
                "updated_at": datetime.utcnow().isoformat(),
            },
            on_conflict="business_id"
        ).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_business(business_id: str) -> dict | None:
        """Get Google Wallet class for a business."""
        db = get_db()
        result = db.table("google_wallet_classes").select("*").eq(
            "business_id", business_id
        ).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_class_id(class_id: str) -> dict | None:
        """Get Google Wallet class by class_id."""
        db = get_db()
        result = db.table("google_wallet_classes").select("*").eq(
            "class_id", class_id
        ).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def delete(business_id: str) -> bool:
        """Delete Google Wallet class for a business."""
        db = get_db()
        result = db.table("google_wallet_classes").delete().eq(
            "business_id", business_id
        ).execute()
        return bool(result.data)


class GoogleNotificationRepository:
    """Database operations for tracking Google Wallet notifications (rate limiting)."""

    @staticmethod
    @with_retry()
    def record_notification(
        customer_id: str,
        google_object_id: str,
        notification_type: str = "stamp"
    ) -> dict | None:
        """
        Record a notification sent to track rate limits.

        Args:
            customer_id: The customer UUID
            google_object_id: The Google Wallet object ID
            notification_type: Type of notification (stamp, reward, design)

        Returns:
            The created record
        """
        db = get_db()
        result = db.table("google_wallet_notifications").insert({
            "customer_id": customer_id,
            "google_object_id": google_object_id,
            "notification_type": notification_type,
        }).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_notification_count_last_24h(customer_id: str) -> int:
        """
        Get count of notifications sent in the last 24 hours for a customer.

        Google limits notifications to 3 per pass per 24 hours.

        Returns:
            Count of notifications in last 24 hours
        """
        db = get_db()
        since = (datetime.utcnow() - timedelta(hours=24)).isoformat()

        result = db.table("google_wallet_notifications").select(
            "id", count="exact"
        ).eq("customer_id", customer_id).gte("created_at", since).execute()

        return result.count if result.count else 0

    @staticmethod
    @with_retry()
    def cleanup_old_notifications() -> int:
        """
        Delete notifications older than 24 hours.

        Returns:
            Number of deleted records
        """
        db = get_db()
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()

        result = db.table("google_wallet_notifications").delete().lt(
            "created_at", cutoff
        ).execute()

        return len(result.data) if result.data else 0

    @staticmethod
    def should_notify(customer_id: str, stamps: int, max_stamps: int) -> bool:
        """
        Determine if we should send a notification based on rate limits.

        Google allows max 3 notifications per pass per 24 hours.
        We prioritize reward events (always notify) and use remaining
        quota for regular stamp notifications.

        Args:
            customer_id: Customer UUID
            stamps: Current stamp count
            max_stamps: Maximum stamps for reward

        Returns:
            True if notification should be sent
        """
        # Always notify on reward reached or redeemed (stamps reset to 0)
        if stamps == max_stamps or stamps == 0:
            return True

        # Check notification count in last 24h
        count = GoogleNotificationRepository.get_notification_count_last_24h(customer_id)

        # Reserve 1 slot for potential reward notification
        return count < 2
