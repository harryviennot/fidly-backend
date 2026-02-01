from database.connection import get_db, with_retry


class CardDesignRepository:

    @staticmethod
    @with_retry()
    def create(
        business_id: str,
        name: str,
        organization_name: str,
        description: str,
        logo_text: str | None = None,
        foreground_color: str = "rgb(255, 255, 255)",
        background_color: str = "rgb(139, 90, 43)",
        label_color: str = "rgb(255, 255, 255)",
        total_stamps: int = 10,
        stamp_filled_color: str = "rgb(255, 215, 0)",
        stamp_empty_color: str = "rgb(80, 50, 20)",
        stamp_border_color: str = "rgb(255, 255, 255)",
        stamp_icon: str = "checkmark",
        reward_icon: str = "gift",
        icon_color: str = "#ffffff",
        secondary_fields: list | None = None,
        auxiliary_fields: list | None = None,
        back_fields: list | None = None,
    ) -> dict | None:
        """Create a new card design for a business."""
        db = get_db()
        result = db.table("card_designs").insert({
            "business_id": business_id,
            "name": name,
            "organization_name": organization_name,
            "description": description,
            "logo_text": logo_text,
            "foreground_color": foreground_color,
            "background_color": background_color,
            "label_color": label_color,
            "total_stamps": total_stamps,
            "stamp_filled_color": stamp_filled_color,
            "stamp_empty_color": stamp_empty_color,
            "stamp_border_color": stamp_border_color,
            "stamp_icon": stamp_icon,
            "reward_icon": reward_icon,
            "icon_color": icon_color,
            "secondary_fields": secondary_fields or [],
            "auxiliary_fields": auxiliary_fields or [],
            "back_fields": back_fields or [],
        }).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_id(design_id: str) -> dict | None:
        """Get a card design by ID."""
        db = get_db()
        result = db.table("card_designs").select("*").eq("id", design_id).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_active(business_id: str) -> dict | None:
        """Get the active card design for a business."""
        db = get_db()
        result = db.table("card_designs").select("*").eq(
            "business_id", business_id
        ).eq("is_active", True).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_all(business_id: str) -> list[dict]:
        """Get all card designs for a business ordered by creation date."""
        db = get_db()
        result = db.table("card_designs").select("*").eq(
            "business_id", business_id
        ).order("created_at", desc=True).execute()
        return result.data if result and result.data else []

    @staticmethod
    @with_retry()
    def update(design_id: str, **kwargs) -> dict | None:
        """Update a card design. Only updates provided fields."""
        if not kwargs:
            return CardDesignRepository.get_by_id(design_id)

        db = get_db()
        result = db.table("card_designs").update(kwargs).eq("id", design_id).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def delete(design_id: str) -> bool:
        """Delete a card design. Returns True if deleted."""
        db = get_db()
        result = db.table("card_designs").delete().eq("id", design_id).execute()
        return bool(result and result.data and len(result.data) > 0)

    @staticmethod
    @with_retry()
    def set_active(business_id: str, design_id: str) -> dict | None:
        """Set a design as active, deactivating all others for this business."""
        db = get_db()
        # Deactivate all designs for this business
        db.table("card_designs").update({
            "is_active": False
        }).eq("business_id", business_id).execute()

        # Activate the specified design
        result = db.table("card_designs").update({
            "is_active": True
        }).eq("id", design_id).execute()

        return result.data[0] if result and result.data else None
