from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.core.permissions import get_current_user_profile
from app.domain.schemas import OnboardingProgressCreate, OnboardingProgressResponse
from app.repositories.onboarding import OnboardingRepository
from app.services.storage import get_storage_service

router = APIRouter()

# Maximum file size: 2MB
MAX_FILE_SIZE = 2 * 1024 * 1024
ALLOWED_CONTENT_TYPES = ["image/png"]


@router.post("", response_model=OnboardingProgressResponse)
def save_onboarding_progress(
    data: OnboardingProgressCreate,
    current_user: dict = Depends(get_current_user_profile)
):
    """Save or update onboarding progress for the current user.

    This endpoint allows authenticated users to save their onboarding
    progress so they can resume later, even on a different device.
    """
    progress_data = {
        "business_name": data.business_name,
        "url_slug": data.url_slug,
        "owner_name": data.owner_name,
        "category": data.category,
        "description": data.description,
        "email": data.email,
        "card_design": data.card_design.model_dump() if data.card_design else None,
        "current_step": data.current_step,
        "completed_steps": data.completed_steps,
    }

    progress = OnboardingRepository.upsert(current_user["id"], **progress_data)
    if not progress:
        raise HTTPException(status_code=500, detail="Failed to save onboarding progress")

    return OnboardingProgressResponse(**progress)


@router.get("", response_model=OnboardingProgressResponse | None)
def get_onboarding_progress(
    current_user: dict = Depends(get_current_user_profile)
):
    """Get the current user's onboarding progress.

    Returns null if no progress has been saved yet.
    """
    progress = OnboardingRepository.get_by_user_id(current_user["id"])
    if not progress:
        return None

    return OnboardingProgressResponse(**progress)


@router.delete("")
def delete_onboarding_progress(
    current_user: dict = Depends(get_current_user_profile)
):
    """Delete the current user's onboarding progress.

    Called after successfully completing onboarding.
    """
    deleted = OnboardingRepository.delete(current_user["id"])
    return {"success": deleted, "message": "Onboarding progress cleared" if deleted else "No progress to delete"}


@router.post("/upload/logo")
async def upload_onboarding_logo(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user_profile)
):
    """Upload a logo image during onboarding.

    The logo is stored in Supabase Storage at onboarding/{user_id}/logo.png.
    The URL is also saved in the user's onboarding progress.
    """
    # Validate content type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )

    # Read file content
    file_data = await file.read()

    # Validate file size
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )

    # Upload to Supabase Storage
    storage = get_storage_service()
    try:
        url = storage.upload_onboarding_logo(current_user["id"], file_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

    # Update onboarding progress with logo URL
    progress = OnboardingRepository.get_by_user_id(current_user["id"])
    if progress:
        card_design = progress.get("card_design") or {}
        card_design["logo_url"] = url
        OnboardingRepository.upsert(
            current_user["id"],
            card_design=card_design,
            **{k: v for k, v in progress.items() if k not in ["id", "user_id", "card_design", "created_at", "updated_at"]}
        )

    return {"url": url, "message": "Logo uploaded successfully"}


@router.delete("/upload/logo")
def delete_onboarding_logo(
    current_user: dict = Depends(get_current_user_profile)
):
    """Delete the current user's onboarding logo.

    Removes the logo from Supabase Storage and clears the URL from progress.
    """
    storage = get_storage_service()

    # Delete from storage
    deleted = storage.delete_onboarding_logo(current_user["id"])

    # Clear URL from onboarding progress
    progress = OnboardingRepository.get_by_user_id(current_user["id"])
    if progress:
        card_design = progress.get("card_design") or {}
        if "logo_url" in card_design:
            del card_design["logo_url"]
            OnboardingRepository.upsert(
                current_user["id"],
                card_design=card_design if card_design else None,
                **{k: v for k, v in progress.items() if k not in ["id", "user_id", "card_design", "created_at", "updated_at"]}
            )

    return {"success": deleted, "message": "Logo deleted" if deleted else "No logo to delete"}
