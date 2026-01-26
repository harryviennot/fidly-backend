from fastapi import APIRouter, HTTPException, Depends

from app.domain.schemas import BusinessCreate, BusinessUpdate, BusinessResponse
from app.repositories.business import BusinessRepository
from app.repositories.membership import MembershipRepository
from app.core.permissions import (
    get_current_user_profile,
    require_any_access,
    require_owner_access,
    BusinessAccessContext,
)

router = APIRouter()


@router.post("", response_model=BusinessResponse)
def create_business(
    data: BusinessCreate,
    user: dict = Depends(get_current_user_profile)
):
    """Create a new business and assign current user as owner."""
    existing = BusinessRepository.get_by_slug(data.url_slug)
    if existing:
        raise HTTPException(status_code=400, detail="URL slug already taken")

    business = BusinessRepository.create(
        name=data.name,
        url_slug=data.url_slug,
        subscription_tier=data.subscription_tier,
        settings=data.settings,
    )
    if not business:
        raise HTTPException(status_code=500, detail="Failed to create business")

    # Create owner membership for the creating user
    MembershipRepository.create(
        user_id=user["id"],
        business_id=business["id"],
        role="owner"
    )

    return BusinessResponse(**business)


@router.get("", response_model=list[BusinessResponse])
def list_my_businesses(user: dict = Depends(get_current_user_profile)):
    """Get all businesses the current user is a member of."""
    memberships = MembershipRepository.get_user_memberships(user["id"])
    return [BusinessResponse(**m["businesses"]) for m in memberships]


@router.get("/{business_id}", response_model=BusinessResponse)
def get_business(ctx: BusinessAccessContext = Depends(require_any_access)):
    """Get a business by ID (requires membership)."""
    business = BusinessRepository.get_by_id(ctx.business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return BusinessResponse(**business)


@router.get("/slug/{url_slug}", response_model=BusinessResponse)
def get_business_by_slug(url_slug: str):
    """Get a business by URL slug (public for customer-facing pages)."""
    business = BusinessRepository.get_by_slug(url_slug)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return BusinessResponse(**business)


@router.put("/{business_id}", response_model=BusinessResponse)
def update_business(
    data: BusinessUpdate,
    ctx: BusinessAccessContext = Depends(require_owner_access)
):
    """Update a business (requires owner role)."""
    existing = BusinessRepository.get_by_id(ctx.business_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Business not found")

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return BusinessResponse(**existing)

    business = BusinessRepository.update(ctx.business_id, **update_data)
    if not business:
        raise HTTPException(status_code=500, detail="Failed to update business")
    return BusinessResponse(**business)


@router.delete("/{business_id}")
def delete_business(ctx: BusinessAccessContext = Depends(require_owner_access)):
    """Delete a business (requires owner role)."""
    existing = BusinessRepository.get_by_id(ctx.business_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Business not found")

    deleted = BusinessRepository.delete(ctx.business_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete business")
    return {"message": "Business deleted successfully"}
