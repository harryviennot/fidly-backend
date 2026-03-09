"""
EventService: Manages promotional events and calculates modifiers.
"""

import logging
from datetime import datetime, timezone

from database.connection import get_db, with_retry
from app.services.programs.types import EventModifiers

logger = logging.getLogger(__name__)


class EventService:
    """Service for managing promotional events."""

    @staticmethod
    @with_retry()
    def get_active_events(
        business_id: str,
        program_id: str | None = None,
    ) -> list[dict]:
        """Get currently active events for a business/program."""
        db = get_db()
        now = datetime.now(timezone.utc).isoformat()

        query = (
            db.table("promotional_events")
            .select("*")
            .eq("business_id", business_id)
            .eq("is_active", True)
            .lte("starts_at", now)
            .gte("ends_at", now)
        )

        if program_id:
            # Events for this specific program OR events with no program (business-wide)
            query = query.or_(f"program_id.eq.{program_id},program_id.is.null")

        result = query.execute()
        return result.data if result and result.data else []

    @staticmethod
    def calculate_modifiers(events: list[dict]) -> EventModifiers:
        """Calculate combined modifiers from a list of active events."""
        multiplier = 1.0
        bonus = 0

        for event in events:
            config = event.get("config", {})
            event_type = event.get("type", "")

            if event_type == "multiplier":
                # Multipliers stack multiplicatively
                multiplier *= config.get("multiplier", 1.0)
            elif event_type == "bonus":
                # Bonuses stack additively
                bonus += config.get("bonus_stamps", 0)

        return EventModifiers(multiplier=multiplier, bonus=bonus)

    @staticmethod
    @with_retry()
    def create_event(
        business_id: str,
        name: str,
        type: str,
        config: dict,
        starts_at: str,
        ends_at: str,
        program_id: str | None = None,
        description: str | None = None,
        announcement_title: str | None = None,
        announcement_body: str | None = None,
    ) -> dict | None:
        db = get_db()
        data = {
            "business_id": business_id,
            "name": name,
            "type": type,
            "config": config,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "is_active": True,
        }
        if program_id:
            data["program_id"] = program_id
        if description:
            data["description"] = description
        if announcement_title:
            data["announcement_title"] = announcement_title
        if announcement_body:
            data["announcement_body"] = announcement_body

        result = db.table("promotional_events").insert(data).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def list_events(business_id: str) -> list[dict]:
        db = get_db()
        result = (
            db.table("promotional_events")
            .select("*")
            .eq("business_id", business_id)
            .order("starts_at", desc=True)
            .execute()
        )
        return result.data if result and result.data else []

    @staticmethod
    @with_retry()
    def update_event(event_id: str, **kwargs) -> dict | None:
        db = get_db()
        result = db.table("promotional_events").update(kwargs).eq("id", event_id).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def delete_event(event_id: str) -> bool:
        db = get_db()
        result = db.table("promotional_events").delete().eq("id", event_id).execute()
        return bool(result and result.data and len(result.data) > 0)
