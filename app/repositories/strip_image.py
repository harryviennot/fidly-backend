"""
Repository for pre-generated strip image URLs.
Manages strip_images table for both Apple and Google Wallet.
"""

from typing import Literal
from database.connection import get_db, with_retry


Platform = Literal["apple", "google"]
Resolution = Literal["1x", "2x", "3x", "hero"]


class StripImageRepository:
    """Repository for managing pre-generated strip image URLs."""

    @staticmethod
    @with_retry()
    def get_url(
        design_id: str,
        stamp_count: int,
        platform: Platform,
        resolution: Resolution = "3x"
    ) -> str | None:
        """Get a pre-generated strip image URL."""
        db = get_db()
        result = db.table("strip_images").select("url").eq(
            "design_id", design_id
        ).eq("stamp_count", stamp_count).eq(
            "platform", platform
        ).eq("resolution", resolution).limit(1).execute()

        if result.data:
            return result.data[0]["url"]
        return None

    @staticmethod
    @with_retry()
    def get_all_for_design(design_id: str) -> list[dict]:
        """Get all strip images for a design."""
        db = get_db()
        result = db.table("strip_images").select("*").eq(
            "design_id", design_id
        ).order("stamp_count").order("platform").order("resolution").execute()
        return result.data

    @staticmethod
    @with_retry()
    def get_apple_urls(design_id: str, stamp_count: int) -> dict[str, str]:
        """
        Get all Apple Wallet strip URLs for a specific stamp count.
        Returns dict like {'1x': 'url', '2x': 'url', '3x': 'url'}
        """
        db = get_db()
        result = db.table("strip_images").select("resolution, url").eq(
            "design_id", design_id
        ).eq("stamp_count", stamp_count).eq("platform", "apple").execute()

        return {row["resolution"]: row["url"] for row in result.data}

    @staticmethod
    @with_retry()
    def get_google_hero_url(design_id: str, stamp_count: int) -> str | None:
        """Get Google Wallet hero image URL for a specific stamp count."""
        return StripImageRepository.get_url(
            design_id=design_id,
            stamp_count=stamp_count,
            platform="google",
            resolution="hero"
        )

    @staticmethod
    @with_retry()
    def upsert(
        design_id: str,
        stamp_count: int,
        platform: Platform,
        resolution: Resolution,
        url: str
    ) -> dict:
        """Insert or update a strip image URL."""
        db = get_db()
        result = db.table("strip_images").upsert({
            "design_id": design_id,
            "stamp_count": stamp_count,
            "platform": platform,
            "resolution": resolution,
            "url": url,
        }, on_conflict="design_id,stamp_count,platform,resolution").execute()

        return result.data[0] if result.data else {}

    @staticmethod
    @with_retry()
    def upsert_batch(records: list[dict]) -> int:
        """
        Batch upsert multiple strip image records.
        Each record should have: design_id, stamp_count, platform, resolution, url

        Returns number of records upserted.
        """
        if not records:
            return 0

        db = get_db()
        result = db.table("strip_images").upsert(
            records,
            on_conflict="design_id,stamp_count,platform,resolution"
        ).execute()

        return len(result.data) if result.data else 0

    @staticmethod
    @with_retry()
    def delete_for_design(design_id: str) -> int:
        """
        Delete all strip images for a design.
        Used when regenerating strips.

        Returns number of records deleted.
        """
        db = get_db()
        result = db.table("strip_images").delete().eq(
            "design_id", design_id
        ).execute()

        return len(result.data) if result.data else 0

    @staticmethod
    @with_retry()
    def exists_for_design(design_id: str) -> bool:
        """Check if any strip images exist for a design."""
        db = get_db()
        result = db.table("strip_images").select("id").eq(
            "design_id", design_id
        ).limit(1).execute()

        return len(result.data) > 0

    @staticmethod
    @with_retry()
    def count_for_design(design_id: str) -> int:
        """Count strip images for a design."""
        db = get_db()
        result = db.table("strip_images").select("id", count="exact").eq(
            "design_id", design_id
        ).execute()

        return result.count if result.count is not None else 0
