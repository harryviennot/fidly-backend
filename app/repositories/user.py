from database.connection import get_db


class UserRepository:

    @staticmethod
    def create(email: str, name: str, avatar_url: str | None = None) -> dict | None:
        """Create a new user."""
        db = get_db()
        result = db.table("users").insert({
            "email": email,
            "name": name,
            "avatar_url": avatar_url,
        }).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    def get_by_id(user_id: str) -> dict | None:
        """Get a user by ID."""
        db = get_db()
        result = db.table("users").select("*").eq("id", user_id).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    def get_by_email(email: str) -> dict | None:
        """Get a user by email."""
        db = get_db()
        result = db.table("users").select("*").eq("email", email).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    def get_by_auth_id(auth_id: str) -> dict | None:
        """Get a user by Supabase auth ID."""
        db = get_db()
        result = db.table("users").select("*").eq("auth_id", auth_id).limit(1).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    def get_all() -> list[dict]:
        """Get all users."""
        db = get_db()
        result = db.table("users").select("*").order("created_at", desc=True).execute()
        return result.data if result and result.data else []

    @staticmethod
    def update(user_id: str, **kwargs) -> dict | None:
        """Update a user."""
        db = get_db()
        result = db.table("users").update(kwargs).eq("id", user_id).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    def delete(user_id: str) -> bool:
        """Delete a user."""
        db = get_db()
        result = db.table("users").delete().eq("id", user_id).execute()
        return bool(result and result.data and len(result.data) > 0)
