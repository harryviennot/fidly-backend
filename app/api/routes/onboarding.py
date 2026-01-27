from fastapi import APIRouter, Depends, HTTPException

from app.core.permissions import get_current_user_profile
from app.domain.schemas import OnboardingProgressCreate, OnboardingProgressResponse
from app.repositories.onboarding import OnboardingRepository

router = APIRouter()


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
