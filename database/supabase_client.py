from functools import lru_cache

from supabase import create_client, Client

from app.core.config import settings


@lru_cache
def get_supabase_client() -> Client:
    """Get the Supabase client singleton using the secret key for server-side operations."""
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise RuntimeError(
            "Supabase credentials not configured. "
            "Set SUPABASE_URL and SUPABASE_SECRET_KEY environment variables."
        )
    return create_client(settings.supabase_url, settings.supabase_secret_key)
