import re

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile

from app.domain.schemas import BusinessCreate, BusinessUpdate, BusinessResponse
from app.repositories.business import BusinessRepository
from app.repositories.membership import MembershipRepository
from app.repositories.onboarding import OnboardingRepository
from app.repositories.card_design import CardDesignRepository
from app.core.permissions import (
    get_current_user_profile,
    require_any_access,
    require_owner_access,
    BusinessAccessContext,
)
from app.services.storage import get_storage_service
from app.services.onboarding_mapper import map_onboarding_to_card_design

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

    # Handle logo: either copy from onboarding bucket or upload base64 directly
    if data.logo_url:
        storage = get_storage_service()
        new_logo_url = None

        if data.logo_url.startswith("data:"):
            # Base64 data URL - upload directly to businesses bucket
            new_logo_url = storage.upload_base64_logo_to_business(
                base64_data=data.logo_url,
                business_id=business["id"]
            )
        elif "onboarding" in data.logo_url:
            # Onboarding bucket URL - copy to businesses bucket
            new_logo_url = storage.copy_onboarding_logo_to_business(
                user_id=user["auth_id"],
                business_id=business["id"]
            )

        if new_logo_url:
            BusinessRepository.update(business["id"], logo_url=new_logo_url)
            business["logo_url"] = new_logo_url

    # Auto-create card design from onboarding data
    # Note: onboarding_progress.user_id references users.id, not auth_id
    onboarding = OnboardingRepository.get_by_user_id(user["id"])
    if onboarding:
        card_design_data = onboarding.get("card_design")
        category = onboarding.get("category")

        # Map onboarding data to card design format
        design_payload = map_onboarding_to_card_design(
            card_design_data=card_design_data,
            business_name=data.name,
            category=category,
        )

        # Create the card design (not active - user will activate manually)
        CardDesignRepository.create(
            business_id=business["id"],
            **design_payload
        )

    return BusinessResponse(**business)


@router.get("", response_model=list[BusinessResponse])
def list_my_businesses(user: dict = Depends(get_current_user_profile)):
    """Get all businesses the current user is a member of."""
    memberships = MembershipRepository.get_user_memberships(user["id"])
    return [BusinessResponse(**m["businesses"]) for m in memberships]


# Slug routes MUST come before /{business_id} to avoid path conflicts
@router.get("/slug/{url_slug}/available")
def check_slug_availability(url_slug: str):
    """Check if a URL slug is available (public, no auth required)."""
    # Validate slug format
    if not url_slug or len(url_slug) < 3:
        return {"available": False, "reason": "Slug must be at least 3 characters"}

    if len(url_slug) > 50:
        return {"available": False, "reason": "Slug must be 50 characters or less"}

    # Check if slug contains only valid characters
    if not re.match(r'^[a-z0-9-]+$', url_slug):
        return {"available": False, "reason": "Slug can only contain lowercase letters, numbers, and hyphens"}

    business = BusinessRepository.get_by_slug(url_slug)
    if business:
        return {"available": False, "reason": "This URL is already taken"}

    return {"available": True}


@router.get("/slug/{url_slug}", response_model=BusinessResponse)
def get_business_by_slug(url_slug: str):
    """Get a business by URL slug (public for customer-facing pages)."""
    business = BusinessRepository.get_by_slug(url_slug)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return BusinessResponse(**business)


# Dynamic ID routes come after static/slug routes
@router.get("/{business_id}", response_model=BusinessResponse)
def get_business(ctx: BusinessAccessContext = Depends(require_any_access)):
    """Get a business by ID (requires membership)."""
    business = BusinessRepository.get_by_id(ctx.business_id)
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


@router.post("/{business_id}/logo")
async def upload_business_logo(
    file: UploadFile = File(...),
    ctx: BusinessAccessContext = Depends(require_owner_access),
):
    """Upload a new logo for the business (deletes old one first)."""
    # Validate file type
    if file.content_type not in ["image/png", "image/jpeg"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PNG and JPG are allowed."
        )

    # Validate file size (max 2MB)
    file_data = await file.read()
    if len(file_data) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 2MB."
        )

    storage = get_storage_service()

    # Delete old logo if it exists
    existing = BusinessRepository.get_by_id(ctx.business_id)
    if existing and existing.get("logo_url"):
        old_path = f"{ctx.business_id}/logo.png"
        storage.delete_file(storage.BUSINESSES_BUCKET, old_path)

    # Upload new logo
    new_url = storage.upload_business_logo(ctx.business_id, file_data)
    if not new_url:
        raise HTTPException(status_code=500, detail="Failed to upload logo")

    # Update business record
    BusinessRepository.update(ctx.business_id, logo_url=new_url)

    return {"url": new_url}


@router.delete("/{business_id}/logo")
def delete_business_logo(ctx: BusinessAccessContext = Depends(require_owner_access)):
    """Delete the business logo."""
    existing = BusinessRepository.get_by_id(ctx.business_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Business not found")

    if not existing.get("logo_url"):
        return {"message": "No logo to delete"}

    storage = get_storage_service()

    # Delete the logo file
    path = f"{ctx.business_id}/logo.png"
    storage.delete_file(storage.BUSINESSES_BUCKET, path)

    # Clear logo_url in database
    BusinessRepository.update(ctx.business_id, logo_url=None)

    return {"message": "Logo deleted successfully"}
