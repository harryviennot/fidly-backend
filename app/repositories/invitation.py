import secrets
from datetime import datetime, timedelta, timezone

from database.connection import get_db, with_retry


class InvitationRepository:
    """Repository for managing team invitations."""

    @staticmethod
    @with_retry()
    def create(
        business_id: str,
        email: str,
        role: str,
        invited_by: str,
        name: str | None = None,
        expires_days: int = 7
    ) -> dict | None:
        """Create a new invitation with a unique token."""
        db = get_db()
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

        result = db.table("invitations").insert({
            "business_id": business_id,
            "email": email.lower(),
            "name": name,
            "role": role,
            "token": token,
            "invited_by": invited_by,
            "status": "pending",
            "expires_at": expires_at.isoformat(),
        }).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_token(token: str) -> dict | None:
        """Get an invitation by token, including business and inviter details."""
        db = get_db()
        result = db.table("invitations").select(
            "*, businesses(*), users!invited_by(id, name, email)"
        ).eq("token", token).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_id(invitation_id: str) -> dict | None:
        """Get an invitation by ID."""
        db = get_db()
        result = db.table("invitations").select("*").eq("id", invitation_id).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_pending_for_business(business_id: str) -> list[dict]:
        """Get all pending invitations for a business."""
        db = get_db()
        result = db.table("invitations").select(
            "*, users!invited_by(id, name, email)"
        ).eq("business_id", business_id).eq(
            "status", "pending"
        ).order("created_at", desc=True).execute()
        return result.data if result and result.data else []

    @staticmethod
    @with_retry()
    def get_pending_by_email(email: str, business_id: str) -> dict | None:
        """Check if a pending invitation exists for this email and business."""
        db = get_db()
        result = db.table("invitations").select("*").eq(
            "email", email.lower()
        ).eq("business_id", business_id).eq(
            "status", "pending"
        ).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def mark_accepted(invitation_id: str) -> dict | None:
        """Mark an invitation as accepted."""
        db = get_db()
        result = db.table("invitations").update({
            "status": "accepted",
            "accepted_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", invitation_id).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def mark_cancelled(invitation_id: str) -> dict | None:
        """Mark an invitation as cancelled."""
        db = get_db()
        result = db.table("invitations").update({
            "status": "cancelled"
        }).eq("id", invitation_id).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def delete(invitation_id: str) -> bool:
        """Delete an invitation."""
        db = get_db()
        result = db.table("invitations").delete().eq("id", invitation_id).execute()
        return bool(result and result.data and len(result.data) > 0)

    @staticmethod
    @with_retry()
    def count_pending_by_role(business_id: str, role: str) -> int:
        """Count pending invitations for a specific role."""
        db = get_db()
        result = db.table("invitations").select(
            "id", count="exact"
        ).eq("business_id", business_id).eq(
            "role", role
        ).eq("status", "pending").execute()
        return result.count if result and result.count is not None else 0

    @staticmethod
    def is_expired(invitation: dict) -> bool:
        """Check if an invitation has expired."""
        expires_at_str = invitation.get("expires_at")
        if not expires_at_str:
            return True

        # Handle both ISO formats with and without timezone
        expires_at_str = expires_at_str.replace("Z", "+00:00")
        expires_at = datetime.fromisoformat(expires_at_str)

        # Ensure we compare timezone-aware datetimes
        now = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return now > expires_at
