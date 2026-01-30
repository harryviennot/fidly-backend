import functools
import logging
import time
from typing import Callable, TypeVar

import httpx
from supabase import Client

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


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


def with_retry(max_retries: int = 2, delay: float = 0.1) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that retries database operations on connection errors.

    Handles transient HTTP connection errors like "Server disconnected" by
    resetting the connection and retrying.

    Args:
        max_retries: Maximum number of retry attempts (default 2)
        delay: Delay in seconds between retries (default 0.1)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            from .supabase_client import reset_supabase_client

            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (httpx.RemoteProtocolError, httpx.ConnectError) as e:
                    last_error = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Connection error in {func.__name__}, retrying ({attempt + 1}/{max_retries}): {e}"
                        )
                        reset_supabase_client()
                        time.sleep(delay)
                    else:
                        logger.error(f"Connection error in {func.__name__} after {max_retries} retries: {e}")
                        raise
            raise last_error  # Should never reach here, but for type safety
        return wrapper
    return decorator
