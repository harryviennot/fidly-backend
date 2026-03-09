from database.connection import get_db, with_retry


class ProgramRepository:

    @staticmethod
    @with_retry()
    def create(
        business_id: str,
        name: str,
        type: str = "stamp",
        is_active: bool = True,
        is_default: bool = False,
        config: dict | None = None,
        reward_name: str | None = None,
        reward_description: str | None = None,
        back_fields: list | None = None,
        translations: dict | None = None,
    ) -> dict | None:
        db = get_db()
        data = {
            "business_id": business_id,
            "name": name,
            "type": type,
            "is_active": is_active,
            "is_default": is_default,
            "config": config or {},
            "back_fields": back_fields or [],
            "translations": translations or {},
        }
        if reward_name:
            data["reward_name"] = reward_name
        if reward_description:
            data["reward_description"] = reward_description
        result = db.table("loyalty_programs").insert(data).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_id(program_id: str) -> dict | None:
        db = get_db()
        result = db.table("loyalty_programs").select("*").eq("id", program_id).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_default(business_id: str) -> dict | None:
        """Get the default program for a business."""
        db = get_db()
        result = (
            db.table("loyalty_programs")
            .select("*")
            .eq("business_id", business_id)
            .eq("is_default", True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_active(business_id: str) -> list[dict]:
        """Get all active programs for a business."""
        db = get_db()
        result = (
            db.table("loyalty_programs")
            .select("*")
            .eq("business_id", business_id)
            .eq("is_active", True)
            .order("created_at")
            .execute()
        )
        return result.data if result and result.data else []

    @staticmethod
    @with_retry()
    def list_by_business(business_id: str) -> list[dict]:
        """Get all programs for a business."""
        db = get_db()
        result = (
            db.table("loyalty_programs")
            .select("*")
            .eq("business_id", business_id)
            .order("created_at")
            .execute()
        )
        return result.data if result and result.data else []

    @staticmethod
    @with_retry()
    def update(program_id: str, **kwargs) -> dict | None:
        db = get_db()
        result = db.table("loyalty_programs").update(kwargs).eq("id", program_id).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def activate(program_id: str) -> dict | None:
        return ProgramRepository.update(program_id, is_active=True)

    @staticmethod
    @with_retry()
    def deactivate(program_id: str) -> dict | None:
        return ProgramRepository.update(program_id, is_active=False)

    @staticmethod
    @with_retry()
    def delete(program_id: str) -> bool:
        db = get_db()
        result = db.table("loyalty_programs").delete().eq("id", program_id).execute()
        return bool(result and result.data and len(result.data) > 0)
