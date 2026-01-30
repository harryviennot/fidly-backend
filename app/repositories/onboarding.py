from database.connection import get_db, with_retry


class OnboardingRepository:
    """Repository for onboarding progress data.

    Note: This requires an 'onboarding_progress' table in Supabase with:
    - id: uuid (primary key)
    - user_id: uuid (foreign key to users.id, unique)
    - business_name: text
    - url_slug: text
    - owner_name: text (nullable)
    - category: text (nullable)
    - description: text (nullable)
    - email: text (nullable)
    - card_design: jsonb (nullable)
    - current_step: int
    - completed_steps: int[] (array of integers)
    - created_at: timestamp
    - updated_at: timestamp
    """

    @staticmethod
    @with_retry()
    def upsert(user_id: str, **kwargs) -> dict | None:
        """Create or update onboarding progress for a user."""
        db = get_db()

        # Check if progress exists
        existing = OnboardingRepository.get_by_user_id(user_id)

        if existing:
            # Update existing
            result = db.table("onboarding_progress").update({
                **kwargs,
                "updated_at": "now()"
            }).eq("user_id", user_id).execute()
        else:
            # Insert new
            result = db.table("onboarding_progress").insert({
                "user_id": user_id,
                **kwargs
            }).execute()

        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def get_by_user_id(user_id: str) -> dict | None:
        """Get onboarding progress for a user."""
        db = get_db()
        result = db.table("onboarding_progress").select("*").eq("user_id", user_id).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def delete(user_id: str) -> bool:
        """Delete onboarding progress for a user (after they complete onboarding)."""
        db = get_db()
        result = db.table("onboarding_progress").delete().eq("user_id", user_id).execute()
        return bool(result and result.data and len(result.data) > 0)
