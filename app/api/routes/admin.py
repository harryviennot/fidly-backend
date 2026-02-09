"""Superadmin-only API routes for platform administration."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import require_superadmin
from app.repositories.business import BusinessRepository
from app.repositories.membership import MembershipRepository
from app.repositories.user import UserRepository
from app.services.email import get_email_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/businesses")
def list_all_businesses(
    status: Optional[str] = Query(None, pattern=r'^(pending|active|suspended)$'),
    _: dict = Depends(require_superadmin),
):
    """List all businesses with owner info (superadmin only)."""
    businesses = BusinessRepository.get_all(status=status)

    # Enrich each business with owner info
    enriched = []
    for biz in businesses:
        owner_name = None
        owner_email = None
        try:
            members = MembershipRepository.get_business_members(biz["id"])
            owner = next((m for m in members if m["role"] == "owner"), None)
            if owner and owner.get("users"):
                owner_name = owner["users"].get("name")
                owner_email = owner["users"].get("email")
        except Exception:
            pass

        enriched.append({
            **biz,
            "owner_name": owner_name,
            "owner_email": owner_email,
        })

    return enriched


@router.post("/businesses/{business_id}/activate")
def activate_business(
    business_id: str,
    _: dict = Depends(require_superadmin),
):
    """Activate a pending business (superadmin only). Sends activation email to owner."""
    business = BusinessRepository.get_by_id(business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    if business.get("status") == "active":
        raise HTTPException(status_code=400, detail="Business is already active")

    updated = BusinessRepository.update_status(business_id, "active")
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to activate business")

    # Send activation email to the owner
    try:
        memberships = MembershipRepository.get_business_members(business_id)
        owner = next((m for m in memberships if m["role"] == "owner"), None)
        if owner:
            user = UserRepository.get_by_id(owner["user_id"])
            if user and user.get("email"):
                email_service = get_email_service()
                email_service.send_activation_email(
                    to=user["email"],
                    owner_name=user.get("name", ""),
                    business_name=business["name"],
                )
    except Exception as e:
        logger.error(f"Failed to send activation email for business {business_id}: {e}")
        # Don't fail the activation if email fails

    return updated


@router.post("/businesses/{business_id}/suspend")
def suspend_business(
    business_id: str,
    _: dict = Depends(require_superadmin),
):
    """Suspend a business (superadmin only)."""
    business = BusinessRepository.get_by_id(business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    if business.get("status") == "suspended":
        raise HTTPException(status_code=400, detail="Business is already suspended")

    updated = BusinessRepository.update_status(business_id, "suspended")
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to suspend business")

    return updated
