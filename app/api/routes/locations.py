"""API routes for business locations."""

import logging

from fastapi import APIRouter, HTTPException, Depends

from database.connection import get_db
from app.repositories.business import BusinessRepository
from app.core.permissions import require_management_access, require_owner_access, BusinessAccessContext
from app.core.features import has_feature

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{business_id}")
def list_locations(
    ctx: BusinessAccessContext = Depends(require_management_access),
):
    """List all locations for a business."""
    db = get_db()
    result = (
        db.table("business_locations")
        .select("*")
        .eq("business_id", ctx.business_id)
        .order("created_at")
        .execute()
    )
    return result.data if result and result.data else []


@router.post("/{business_id}")
def create_location(
    body: dict,
    ctx: BusinessAccessContext = Depends(require_owner_access),
):
    """Add a business location."""
    business = BusinessRepository.get_by_id(ctx.business_id)
    tier = business.get("subscription_tier", "pay") if business else "pay"

    if not has_feature(tier, "multiple_locations"):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Pro to add multiple locations",
        )

    db = get_db()
    data = {
        "business_id": ctx.business_id,
        "name": body.get("name", "Main Location"),
        "address": body.get("address"),
        "latitude": body.get("latitude"),
        "longitude": body.get("longitude"),
        "radius_meters": body.get("radius_meters", 100),
        "is_primary": body.get("is_primary", False),
        "metadata": body.get("metadata", {}),
    }
    result = db.table("business_locations").insert(data).execute()
    if not result or not result.data:
        raise HTTPException(status_code=500, detail="Failed to create location")
    return result.data[0]


@router.patch("/{business_id}/{location_id}")
def update_location(
    location_id: str,
    body: dict,
    ctx: BusinessAccessContext = Depends(require_owner_access),
):
    """Update a business location."""
    db = get_db()
    allowed = {"name", "address", "latitude", "longitude", "radius_meters", "is_primary", "metadata"}
    updates = {k: v for k, v in body.items() if k in allowed}

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    result = db.table("business_locations").update(updates).eq("id", location_id).eq("business_id", ctx.business_id).execute()
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Location not found")
    return result.data[0]


@router.delete("/{business_id}/{location_id}")
def delete_location(
    location_id: str,
    ctx: BusinessAccessContext = Depends(require_owner_access),
):
    """Delete a business location."""
    db = get_db()
    result = db.table("business_locations").delete().eq("id", location_id).eq("business_id", ctx.business_id).execute()
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Location not found")
    return {"deleted": True}
