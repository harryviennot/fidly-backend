"""
Redis cache for strip image bytes.

Caches the actual image data to avoid repeated downloads from Supabase Storage
when multiple customers refresh their passes after a design update.
"""

import logging
from typing import Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis connection (lazy initialized)
_redis: Optional[redis.Redis] = None

# Cache TTL: 1 hour (covers the push notification window after design updates)
CACHE_TTL = 3600

# Key prefix for strip images (Apple bytes)
KEY_PREFIX = "strip:"

# Key prefix for Google URLs
GOOGLE_URL_PREFIX = "strip_url:"


def get_redis() -> redis.Redis:
    """Get or create Redis connection."""
    global _redis
    if _redis is None:
        try:
            _redis = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=False,  # We're storing binary image data
            )
            # Test connection
            _redis.ping()
            logger.info("Redis connection established")
        except redis.ConnectionError as e:
            logger.warning(f"Redis connection failed: {e}. Caching disabled.")
            raise
    return _redis


def is_redis_available() -> bool:
    """Check if Redis is available."""
    try:
        get_redis().ping()
        return True
    except Exception:
        return False


def cache_strip_images(
    design_id: str,
    all_strips: dict[int, dict[str, bytes]],
) -> None:
    """
    Cache all strip images for a design after regeneration.

    Called AFTER strips are generated, BEFORE push notifications are sent.
    This ensures all customer pass downloads can use cached bytes.

    Args:
        design_id: The design ID
        all_strips: {stamp_count: {resolution: image_bytes}}
                   e.g., {0: {"1x": bytes, "2x": bytes, "3x": bytes}, 1: {...}, ...}
    """
    try:
        r = get_redis()
        pipe = r.pipeline()

        count = 0
        for stamp_count, resolutions in all_strips.items():
            for resolution, image_data in resolutions.items():
                cache_key = f"{KEY_PREFIX}{design_id}:{stamp_count}:{resolution}"
                pipe.setex(cache_key, CACHE_TTL, image_data)
                count += 1

        pipe.execute()
        logger.info(f"Cached {count} strip images for design {design_id}")

    except Exception as e:
        logger.warning(f"Failed to cache strip images: {e}")
        # Don't raise - caching is optional optimization


def get_cached_strip(
    design_id: str,
    stamp_count: int,
    resolution: str,
) -> Optional[bytes]:
    """
    Get cached strip image bytes.

    Args:
        design_id: The design ID
        stamp_count: Number of filled stamps (0 to total_stamps)
        resolution: "1x", "2x", or "3x" for Apple

    Returns:
        Image bytes if cached, None if not found or cache unavailable
    """
    try:
        cache_key = f"{KEY_PREFIX}{design_id}:{stamp_count}:{resolution}"
        return get_redis().get(cache_key)
    except Exception as e:
        logger.debug(f"Cache miss for {cache_key}: {e}")
        return None


def get_cached_apple_strips(
    design_id: str,
    stamp_count: int,
) -> Optional[dict[str, bytes]]:
    """
    Get all Apple strip resolutions from cache.

    Args:
        design_id: The design ID
        stamp_count: Number of filled stamps

    Returns:
        Dict like {"strip.png": bytes, "strip@2x.png": bytes, "strip@3x.png": bytes}
        or None if any resolution is missing from cache
    """
    try:
        r = get_redis()

        # Map resolution names to file names
        resolution_to_filename = {
            "1x": "strip.png",
            "2x": "strip@2x.png",
            "3x": "strip@3x.png",
        }

        result = {}
        for resolution, filename in resolution_to_filename.items():
            cache_key = f"{KEY_PREFIX}{design_id}:{stamp_count}:{resolution}"
            data = r.get(cache_key)
            if data is None:
                # Cache miss on any resolution means we can't use cache
                return None
            result[filename] = data

        return result

    except Exception as e:
        logger.debug(f"Cache miss for Apple strips: {e}")
        return None


def invalidate_design_cache(design_id: str) -> int:
    """
    Clear all cached images and URLs for a design.

    Called before regenerating strips for a design.

    Args:
        design_id: The design ID

    Returns:
        Number of keys deleted
    """
    try:
        r = get_redis()
        total_deleted = 0

        # Delete Apple strip bytes
        pattern = f"{KEY_PREFIX}{design_id}:*"
        keys = r.keys(pattern)
        if keys:
            total_deleted += r.delete(*keys)

        # Delete Google URLs
        url_pattern = f"{GOOGLE_URL_PREFIX}{design_id}:*"
        url_keys = r.keys(url_pattern)
        if url_keys:
            total_deleted += r.delete(*url_keys)

        if total_deleted:
            logger.info(f"Invalidated {total_deleted} cached strips for design {design_id}")
        return total_deleted
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")
        return 0


def cache_google_urls(design_id: str, urls: dict[int, str]) -> None:
    """
    Cache Google hero URLs for a design after regeneration.

    Args:
        design_id: The design ID
        urls: {stamp_count: url} e.g., {0: "https://...", 1: "https://...", ...}
    """
    try:
        r = get_redis()
        pipe = r.pipeline()

        for stamp_count, url in urls.items():
            cache_key = f"{GOOGLE_URL_PREFIX}{design_id}:{stamp_count}"
            pipe.setex(cache_key, CACHE_TTL, url)

        pipe.execute()
        logger.info(f"Cached {len(urls)} Google URLs for design {design_id}")

    except Exception as e:
        logger.warning(f"Failed to cache Google URLs: {e}")


def get_cached_google_url(design_id: str, stamp_count: int) -> Optional[str]:
    """
    Get cached Google hero URL.

    Args:
        design_id: The design ID
        stamp_count: Number of filled stamps

    Returns:
        URL string if cached, None if not found
    """
    try:
        cache_key = f"{GOOGLE_URL_PREFIX}{design_id}:{stamp_count}"
        result = get_redis().get(cache_key)
        if result:
            # Redis returns bytes, decode to string
            return result.decode("utf-8") if isinstance(result, bytes) else result
        return None
    except Exception as e:
        logger.debug(f"Cache miss for Google URL {cache_key}: {e}")
        return None
