"""API routes for promotional events."""

import logging

from fastapi import APIRouter, HTTPException, Depends

from app.services.programs.events import EventService
from app.repositories.business import BusinessRepository
from app.core.permissions import require_management_access, BusinessAccessContext
from app.core.features import has_feature

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{business_id}")
def list_events(
    ctx: BusinessAccessContext = Depends(require_management_access),
):
    """List all promotional events for a business."""
    return EventService.list_events(ctx.business_id)


@router.post("/{business_id}")
def create_event(
    body: dict,
    ctx: BusinessAccessContext = Depends(require_management_access),
):
    """Create a new promotional event."""
    business = BusinessRepository.get_by_id(ctx.business_id)
    tier = business.get("subscription_tier", "pay") if business else "pay"

    if not has_feature(tier, "promotional_events"):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Pro to create promotional events",
        )

    required = ["name", "type", "config", "starts_at", "ends_at"]
    for field in required:
        if field not in body:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    event = EventService.create_event(
        business_id=ctx.business_id,
        name=body["name"],
        type=body["type"],
        config=body["config"],
        starts_at=body["starts_at"],
        ends_at=body["ends_at"],
        program_id=body.get("program_id"),
        description=body.get("description"),
        announcement_title=body.get("announcement_title"),
        announcement_body=body.get("announcement_body"),
    )
    if not event:
        raise HTTPException(status_code=500, detail="Failed to create event")
    return event


@router.patch("/{business_id}/{event_id}")
def update_event(
    event_id: str,
    body: dict,
    ctx: BusinessAccessContext = Depends(require_management_access),
):
    """Update a promotional event."""
    allowed = {"name", "description", "type", "config", "starts_at", "ends_at",
               "is_active", "announcement_title", "announcement_body", "program_id"}
    updates = {k: v for k, v in body.items() if k in allowed}

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    updated = EventService.update_event(event_id, **updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Event not found")
    return updated


@router.delete("/{business_id}/{event_id}")
def delete_event(
    event_id: str,
    ctx: BusinessAccessContext = Depends(require_management_access),
):
    """Delete a promotional event."""
    deleted = EventService.delete_event(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"deleted": True}
