from fastapi import APIRouter, HTTPException, Depends

from app.domain.schemas import UserCreate, UserUpdate, UserResponse
from app.repositories.user import UserRepository
from app.core.security import require_auth
from app.core.permissions import get_current_user_profile

router = APIRouter()


@router.post("", response_model=UserResponse)
def create_user(data: UserCreate, _caller: dict = Depends(get_current_user_profile)):
    """Create a new user. Caller must be authenticated."""
    existing = UserRepository.get_by_email(data.email)
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    new_user = UserRepository.create(
        email=data.email,
        name=data.name,
        avatar_url=data.avatar_url,
    )
    if not new_user:
        raise HTTPException(status_code=500, detail="Failed to create user")
    return UserResponse(**new_user)


@router.get("", response_model=list[UserResponse])
def list_users(auth: dict = Depends(require_auth)):
    """Get all users (requires authentication)."""
    users = UserRepository.get_all()
    return [UserResponse(**u) for u in users]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, auth: dict = Depends(require_auth)):
    """Get a user by ID (requires authentication)."""
    user = UserRepository.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user)


@router.get("/email/{email}", response_model=UserResponse)
def get_user_by_email(email: str, auth: dict = Depends(require_auth)):
    """Get a user by email (requires authentication)."""
    user = UserRepository.get_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    data: UserUpdate,
    caller: dict = Depends(get_current_user_profile),
):
    """Update a user. Can only update your own profile."""
    if caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="You can only update your own profile")

    existing = UserRepository.get_by_id(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return UserResponse(**existing)

    user = UserRepository.update(user_id, **update_data)
    if not user:
        raise HTTPException(status_code=500, detail="Failed to update user")
    return UserResponse(**user)


@router.delete("/{user_id}")
def delete_user(user_id: str, caller: dict = Depends(get_current_user_profile)):
    """Delete a user. Can only delete your own profile."""
    if caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="You can only delete your own profile")

    existing = UserRepository.get_by_id(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    deleted = UserRepository.delete(user_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete user")
    return {"message": "User deleted successfully"}
