from database.connection import get_db


class BusinessRepository:

    @staticmethod
    def create(
        name: str,
        url_slug: str,
        subscription_tier: str = "pay",
        settings: dict | None = None,
    ) -> dict | None:
        """Create a new business."""
        db = get_db()
        result = db.table("businesses").insert({
            "name": name,
            "url_slug": url_slug,
            "subscription_tier": subscription_tier,
            "settings": settings or {},
        }).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def get_by_id(business_id: str) -> dict | None:
        """Get a business by ID."""
        db = get_db()
        result = db.table("businesses").select("*").eq("id", business_id).maybe_single().execute()
        return result.data

    @staticmethod
    def get_by_slug(url_slug: str) -> dict | None:
        """Get a business by URL slug."""
        db = get_db()
        result = db.table("businesses").select("*").eq("url_slug", url_slug).maybe_single().execute()
        return result.data

    @staticmethod
    def get_all() -> list[dict]:
        """Get all businesses."""
        db = get_db()
        result = db.table("businesses").select("*").order("created_at", desc=True).execute()
        return result.data

    @staticmethod
    def update(business_id: str, **kwargs) -> dict | None:
        """Update a business."""
        db = get_db()
        result = db.table("businesses").update(kwargs).eq("id", business_id).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def delete(business_id: str) -> bool:
        """Delete a business."""
        db = get_db()
        result = db.table("businesses").delete().eq("id", business_id).execute()
        return len(result.data) > 0
