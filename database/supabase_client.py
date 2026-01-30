import threading

from supabase import create_client, Client

from app.core.config import settings

# Thread-local storage for Supabase client to avoid connection pool sharing issues
_thread_local = threading.local()


def get_supabase_client() -> Client:
    """Get a thread-local Supabase client to avoid HTTP/2 connection pool issues.

    Each thread gets its own client instance, preventing "Server disconnected"
    errors that occur when stale pooled connections are reused across threads.
    """
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise RuntimeError(
            "Supabase credentials not configured. "
            "Set SUPABASE_URL and SUPABASE_SECRET_KEY environment variables."
        )

    if not hasattr(_thread_local, "client"):
        _thread_local.client = create_client(
            settings.supabase_url,
            settings.supabase_secret_key,
        )
    return _thread_local.client


def reset_supabase_client() -> None:
    """Reset the thread-local Supabase client.

    Call this after catching a connection error to force a fresh connection
    on the next request.
    """
    if hasattr(_thread_local, "client"):
        delattr(_thread_local, "client")
