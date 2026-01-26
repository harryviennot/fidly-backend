from fastapi import APIRouter, HTTPException

from app.domain.schemas import UserCreate, UserUpdate, UserResponse
from app.repositories.user import UserRepository

router = APIRouter()


@router.post("", response_model=UserResponse)
def create_user(data: UserCreate):
    """Create a new user."""
    existing = UserRepository.get_by_email(data.email)
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    user = UserRepository.create(
        email=data.email,
        name=data.name,
        avatar_url=data.avatar_url,
    )
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create user")
    return UserResponse(**user)


@router.get("", response_model=list[UserResponse])
def list_users():
    """Get all users."""
    users = UserRepository.get_all()
    return [UserResponse(**u) for u in users]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str):
    """Get a user by ID."""
    user = UserRepository.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user)


@router.get("/email/{email}", response_model=UserResponse)
def get_user_by_email(email: str):
    """Get a user by email."""
    user = UserRepository.get_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**user)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: str, data: UserUpdate):
    """Update a user."""
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
def delete_user(user_id: str):
    """Delete a user."""
    existing = UserRepository.get_by_id(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    deleted = UserRepository.delete(user_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete user")
    return {"message": "User deleted successfully"}
