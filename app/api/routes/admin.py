"""Superadmin-only API routes for platform administration."""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import require_superadmin
from app.repositories.business import BusinessRepository
from app.repositories.membership import MembershipRepository
from app.repositories.user import UserRepository
from database.connection import get_db
from app.services.email import get_email_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _month_boundaries():
    """Return ISO strings for start of current month, start of last month, and end of last month."""
    now = datetime.now(timezone.utc)
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 1:
        first_of_last_month = first_of_this_month.replace(year=now.year - 1, month=12)
    else:
        first_of_last_month = first_of_this_month.replace(month=now.month - 1)
    return (
        first_of_this_month.isoformat(),
        first_of_last_month.isoformat(),
        first_of_this_month.isoformat(),  # end of last month = start of this month
    )


def _count(query) -> int:
    """Execute a count query and return the count."""
    result = query.execute()
    return result.count if result.count is not None else 0


@router.get("/stats")
def get_global_stats(
    _: dict = Depends(require_superadmin),
):
    """Global platform statistics (superadmin only)."""
    db = get_db()
    this_month, last_month_start, last_month_end = _month_boundaries()

    # Business counts
    total_biz = _count(db.table("businesses").select("id", count="exact").limit(0))
    active_biz = _count(db.table("businesses").select("id", count="exact").eq("status", "active").limit(0))
    pending_biz = _count(db.table("businesses").select("id", count="exact").eq("status", "pending").limit(0))
    suspended_biz = _count(db.table("businesses").select("id", count="exact").eq("status", "suspended").limit(0))

    # Customer counts
    total_customers = _count(db.table("customers").select("id", count="exact").limit(0))
    customers_this_month = _count(
        db.table("customers").select("id", count="exact").gte("created_at", this_month).limit(0)
    )
    customers_last_month = _count(
        db.table("customers").select("id", count="exact")
        .gte("created_at", last_month_start)
        .lt("created_at", last_month_end)
        .limit(0)
    )

    # Transaction counts (stamps)
    total_stamps = _count(
        db.table("transactions").select("id", count="exact").eq("type", "stamp_added").limit(0)
    )
    stamps_this_month = _count(
        db.table("transactions").select("id", count="exact")
        .eq("type", "stamp_added")
        .gte("created_at", this_month)
        .limit(0)
    )
    stamps_last_month = _count(
        db.table("transactions").select("id", count="exact")
        .eq("type", "stamp_added")
        .gte("created_at", last_month_start)
        .lt("created_at", last_month_end)
        .limit(0)
    )

    # Rewards
    total_rewards = _count(
        db.table("transactions").select("id", count="exact").eq("type", "reward_redeemed").limit(0)
    )

    # Certificate pool
    certs_available = _count(
        db.table("pass_type_ids").select("id", count="exact").eq("status", "available").limit(0)
    )
    certs_assigned = _count(
        db.table("pass_type_ids").select("id", count="exact").eq("status", "assigned").limit(0)
    )

    return {
        "total_businesses": total_biz,
        "active_businesses": active_biz,
        "pending_businesses": pending_biz,
        "suspended_businesses": suspended_biz,
        "total_customers": total_customers,
        "customers_this_month": customers_this_month,
        "customers_last_month": customers_last_month,
        "total_stamps": total_stamps,
        "stamps_this_month": stamps_this_month,
        "stamps_last_month": stamps_last_month,
        "total_rewards_redeemed": total_rewards,
        "certs_available": certs_available,
        "certs_assigned": certs_assigned,
    }


@router.get("/businesses/{business_id}/stats")
def get_business_stats(
    business_id: str,
    _: dict = Depends(require_superadmin),
):
    """Per-business statistics (superadmin only)."""
    business = BusinessRepository.get_by_id(business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    db = get_db()
    this_month, last_month_start, last_month_end = _month_boundaries()

    # Customer counts
    total_customers = _count(
        db.table("customers").select("id", count="exact").eq("business_id", business_id).limit(0)
    )
    customers_this_month = _count(
        db.table("customers").select("id", count="exact")
        .eq("business_id", business_id)
        .gte("created_at", this_month)
        .limit(0)
    )
    customers_last_month = _count(
        db.table("customers").select("id", count="exact")
        .eq("business_id", business_id)
        .gte("created_at", last_month_start)
        .lt("created_at", last_month_end)
        .limit(0)
    )

    # Stamp counts
    total_stamps = _count(
        db.table("transactions").select("id", count="exact")
        .eq("business_id", business_id)
        .eq("type", "stamp_added")
        .limit(0)
    )
    stamps_this_month = _count(
        db.table("transactions").select("id", count="exact")
        .eq("business_id", business_id)
        .eq("type", "stamp_added")
        .gte("created_at", this_month)
        .limit(0)
    )
    stamps_last_month = _count(
        db.table("transactions").select("id", count="exact")
        .eq("business_id", business_id)
        .eq("type", "stamp_added")
        .gte("created_at", last_month_start)
        .lt("created_at", last_month_end)
        .limit(0)
    )

    # Rewards
    total_rewards = _count(
        db.table("transactions").select("id", count="exact")
        .eq("business_id", business_id)
        .eq("type", "reward_redeemed")
        .limit(0)
    )

    # Active design
    active_design = None
    design_result = (
        db.table("card_designs")
        .select("id, name, organization_name, background_color, foreground_color")
        .eq("business_id", business_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if design_result and design_result.data:
        active_design = design_result.data[0]

    # Assigned certificate
    certificate = None
    cert_result = (
        db.table("pass_type_ids")
        .select("id, identifier, status")
        .eq("business_id", business_id)
        .limit(1)
        .execute()
    )
    if cert_result and cert_result.data:
        certificate = cert_result.data[0]

    return {
        "total_customers": total_customers,
        "customers_this_month": customers_this_month,
        "customers_last_month": customers_last_month,
        "total_stamps": total_stamps,
        "stamps_this_month": stamps_this_month,
        "stamps_last_month": stamps_last_month,
        "total_rewards": total_rewards,
        "active_design": active_design,
        "certificate": certificate,
    }


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
