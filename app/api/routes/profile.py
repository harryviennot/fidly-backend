from fastapi import APIRouter, HTTPException, Depends, File, UploadFile

from app.domain.schemas import UserResponse, UserUpdate
from app.repositories.user import UserRepository
from app.core.permissions import get_current_user_profile
from app.services.storage import get_storage_service

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def get_my_profile(user: dict = Depends(get_current_user_profile)):
    """Get the current user's profile."""
    return UserResponse(**user)


@router.put("/me", response_model=UserResponse)
def update_my_profile(
    data: UserUpdate,
    user: dict = Depends(get_current_user_profile),
):
    """Update the current user's profile."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return UserResponse(**user)

    updated_user = UserRepository.update(user["id"], **update_data)
    if not updated_user:
        raise HTTPException(status_code=500, detail="Failed to update profile")
    return UserResponse(**updated_user)


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user_profile),
):
    """Upload a new profile picture for the current user."""
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

    # Delete old avatar if exists
    storage.delete_profile_picture(user["id"])

    # Upload new avatar
    new_url = storage.upload_profile_picture(
        user["id"],
        file_data,
        file.content_type
    )
    if not new_url:
        raise HTTPException(status_code=500, detail="Failed to upload avatar")

    # Update user's avatar_url
    UserRepository.update(user["id"], avatar_url=new_url)

    return {"url": new_url}


@router.delete("/avatar")
def delete_avatar(user: dict = Depends(get_current_user_profile)):
    """Delete the current user's profile picture."""
    if not user.get("avatar_url"):
        return {"message": "No avatar to delete"}

    storage = get_storage_service()

    # Delete the avatar file
    storage.delete_profile_picture(user["id"])

    # Clear avatar_url in database
    UserRepository.update(user["id"], avatar_url=None)

    return {"message": "Avatar deleted successfully"}
