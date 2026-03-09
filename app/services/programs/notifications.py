"""
NotificationService: Handles transactional notifications and promotional messages.
"""

import logging
import re

from database.connection import get_db, with_retry

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notification templates and sending notifications."""

    @staticmethod
    @with_retry()
    def get_templates(program_id: str, trigger: str | None = None) -> list[dict]:
        """Get notification templates for a program, optionally filtered by trigger."""
        db = get_db()
        query = (
            db.table("notification_templates")
            .select("*")
            .eq("program_id", program_id)
            .eq("is_enabled", True)
        )
        if trigger:
            query = query.eq("trigger", trigger)
        result = query.execute()
        return result.data if result and result.data else []

    @staticmethod
    @with_retry()
    def update_template(template_id: str, **kwargs) -> dict | None:
        """Update a notification template."""
        db = get_db()
        kwargs["is_customized"] = True
        result = db.table("notification_templates").update(kwargs).eq("id", template_id).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    def render_template(template: str, context: dict) -> str:
        """Render a template string with {{variable}} placeholders."""
        def replacer(match):
            key = match.group(1).strip()
            return str(context.get(key, match.group(0)))
        return re.sub(r"\{\{(\w+)\}\}", replacer, template)

    async def fire_trigger(
        self,
        program_id: str,
        trigger: str,
        context: dict,
    ) -> list[dict]:
        """
        Fire a notification trigger and render templates.

        Args:
            program_id: The program ID
            trigger: The trigger type (e.g., 'stamp_added', 'reward_earned')
            context: Template variables (customer_name, stamps, remaining, reward_name, etc.)

        Returns:
            List of rendered notifications [{title, body}]
        """
        templates = self.get_templates(program_id, trigger)
        rendered = []

        for template in templates:
            title = self.render_template(template.get("title_template", ""), context)
            body = self.render_template(template.get("body_template", ""), context)
            rendered.append({"title": title, "body": body, "template_id": template["id"]})

        return rendered

    @staticmethod
    @with_retry()
    def create_promotional_message(
        business_id: str,
        title: str,
        body: str,
        target_filter: dict | None = None,
        scheduled_at: str | None = None,
        created_by: str | None = None,
    ) -> dict | None:
        """Create a promotional broadcast message."""
        db = get_db()
        data = {
            "business_id": business_id,
            "title": title,
            "body": body,
            "target_filter": target_filter or {},
            "status": "scheduled" if scheduled_at else "draft",
        }
        if scheduled_at:
            data["scheduled_at"] = scheduled_at
        if created_by:
            data["created_by"] = created_by
        result = db.table("promotional_messages").insert(data).execute()
        return result.data[0] if result and result.data else None

    @staticmethod
    @with_retry()
    def list_promotional_messages(business_id: str) -> list[dict]:
        db = get_db()
        result = (
            db.table("promotional_messages")
            .select("*")
            .eq("business_id", business_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data if result and result.data else []

    @staticmethod
    @with_retry()
    def update_promotional_message(message_id: str, **kwargs) -> dict | None:
        db = get_db()
        result = db.table("promotional_messages").update(kwargs).eq("id", message_id).execute()
        return result.data[0] if result and result.data else None
