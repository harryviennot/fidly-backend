from database.connection import get_db, with_retry


class BusinessRepository:

    @staticmethod
    @with_retry()
    def create(
        name: str,
        url_slug: str,
        subscription_tier: str = "pay",
        settings: dict | None = None,
        logo_url: str | None = None,
    ) -> dict | None:
        """Create a new business."""
        db = get_db()
        data = {
            "name": name,
            "url_slug": url_slug,
            "subscription_tier": subscription_tier,
            "settings": settings or {},
        }
        if logo_url:
            data["logo_url"] = logo_url
        result = db.table("businesses").insert(data).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_id(business_id: str) -> dict | None:
        """Get a business by ID."""
        db = get_db()
        result = db.table("businesses").select("*").eq("id", business_id).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_slug(url_slug: str) -> dict | None:
        """Get a business by URL slug."""
        db = get_db()
        result = db.table("businesses").select("*").eq("url_slug", url_slug).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_all() -> list[dict]:
        """Get all businesses."""
        db = get_db()
        result = db.table("businesses").select("*").order("created_at", desc=True).execute()
        return result.data if result and result.data else []

    @staticmethod
    @with_retry()
    def update(business_id: str, **kwargs) -> dict | None:
        """Update a business."""
        db = get_db()
        result = db.table("businesses").update(kwargs).eq("id", business_id).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def delete(business_id: str) -> bool:
        """Delete a business."""
        db = get_db()
        result = db.table("businesses").delete().eq("id", business_id).execute()
        return bool(result and result.data and len(result.data) > 0)
