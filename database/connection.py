from supabase import Client

from app.core.config import settings


def init_db():
    """Initialize database connection - verify Supabase connection.

    Note: Schema is managed via Supabase migrations, not here.
    """
    if not settings.supabase_url or not settings.supabase_secret_key:
        print("WARNING: Supabase credentials not configured. Database features disabled.")
        return

    try:
        from .supabase_client import get_supabase_client
        client = get_supabase_client()
        # Try a simple query - may fail if migrations haven't run yet
        client.table("businesses").select("id").limit(1).execute()
        print("Supabase connection verified")
    except Exception as e:
        print(f"WARNING: Supabase connection check failed: {e}")
        print("Make sure migrations have been run and credentials are correct.")


def get_db() -> Client:
    """Get database client - Supabase compatible."""
    from .supabase_client import get_supabase_client
    return get_supabase_client()
