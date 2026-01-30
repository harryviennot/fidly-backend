from database.connection import get_db, with_retry


class MembershipRepository:

    @staticmethod
    @with_retry()
    def create(
        user_id: str,
        business_id: str,
        role: str = "scanner",
        invited_by: str | None = None
    ) -> dict | None:
        """Create a membership linking a user to a business."""
        db = get_db()
        data = {
            "user_id": user_id,
            "business_id": business_id,
            "role": role,
        }
        if invited_by:
            data["invited_by"] = invited_by
        result = db.table("memberships").insert(data).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_id(membership_id: str) -> dict | None:
        """Get a membership by ID."""
        db = get_db()
        result = db.table("memberships").select("*").eq("id", membership_id).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_user_memberships(user_id: str) -> list[dict]:
        """Get all memberships for a user with business details."""
        db = get_db()
        result = db.table("memberships").select(
            "*, businesses(*)"
        ).eq("user_id", user_id).execute()
        return result.data if result and result.data else []

    @staticmethod
    @with_retry()
    def get_business_members(business_id: str) -> list[dict]:
        """Get all members of a business with user details."""
        db = get_db()
        result = db.table("memberships").select(
            "*, users!memberships_user_id_fkey(*)"
        ).eq("business_id", business_id).execute()
        return result.data if result and result.data else []

    @staticmethod
    @with_retry()
    def get_membership(user_id: str, business_id: str) -> dict | None:
        """Get a specific membership."""
        db = get_db()
        result = db.table("memberships").select("*").eq(
            "user_id", user_id
        ).eq("business_id", business_id).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def update_role(membership_id: str, role: str) -> dict | None:
        """Update a member's role."""
        db = get_db()
        result = db.table("memberships").update({
            "role": role
        }).eq("id", membership_id).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def delete(membership_id: str) -> bool:
        """Remove a membership."""
        db = get_db()
        result = db.table("memberships").delete().eq("id", membership_id).execute()
        return bool(result and result.data and len(result.data) > 0)

    @staticmethod
    @with_retry()
    def delete_by_user_and_business(user_id: str, business_id: str) -> bool:
        """Remove a membership by user and business IDs."""
        db = get_db()
        result = db.table("memberships").delete().eq(
            "user_id", user_id
        ).eq("business_id", business_id).execute()
        return bool(result and result.data and len(result.data) > 0)
