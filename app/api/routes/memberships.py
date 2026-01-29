from fastapi import APIRouter, HTTPException

from app.domain.schemas import MembershipCreate, MembershipUpdate, MembershipResponse
from app.repositories.membership import MembershipRepository
from app.repositories.user import UserRepository
from app.repositories.business import BusinessRepository

router = APIRouter()


@router.post("", response_model=MembershipResponse)
def create_membership(data: MembershipCreate):
    """Create a membership linking a user to a business."""
    # Verify user exists
    user = UserRepository.get_by_id(data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify business exists
    business = BusinessRepository.get_by_id(data.business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Check if membership already exists
    existing = MembershipRepository.get_membership(data.user_id, data.business_id)
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member of this business")

    membership = MembershipRepository.create(
        user_id=data.user_id,
        business_id=data.business_id,
        role=data.role,
    )
    if not membership:
        raise HTTPException(status_code=500, detail="Failed to create membership")
    return MembershipResponse(**membership)


@router.get("/user/{user_id}", response_model=list[MembershipResponse])
def get_user_memberships(user_id: str):
    """Get all memberships for a user."""
    user = UserRepository.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    memberships = MembershipRepository.get_user_memberships(user_id)
    # Transform 'businesses' key (from Supabase FK join) to 'business' for response schema
    result = []
    for m in memberships:
        membership_data = {**m}
        if "businesses" in membership_data:
            membership_data["business"] = membership_data.pop("businesses")
        result.append(MembershipResponse(**membership_data))
    return result


@router.get("/business/{business_id}", response_model=list[MembershipResponse])
def get_business_members(business_id: str):
    """Get all members of a business."""
    business = BusinessRepository.get_by_id(business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    memberships = MembershipRepository.get_business_members(business_id)
    # Transform 'users' key (from Supabase FK join) to 'user' for response schema
    result = []
    for m in memberships:
        membership_data = {**m}
        if "users" in membership_data:
            membership_data["user"] = membership_data.pop("users")
        result.append(MembershipResponse(**membership_data))
    return result


@router.get("/{membership_id}", response_model=MembershipResponse)
def get_membership(membership_id: str):
    """Get a specific membership."""
    membership = MembershipRepository.get_by_id(membership_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    return MembershipResponse(**membership)


@router.put("/{membership_id}", response_model=MembershipResponse)
def update_membership_role(membership_id: str, data: MembershipUpdate):
    """Update a member's role."""
    existing = MembershipRepository.get_by_id(membership_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Membership not found")

    membership = MembershipRepository.update_role(membership_id, data.role)
    if not membership:
        raise HTTPException(status_code=500, detail="Failed to update membership")
    return MembershipResponse(**membership)


@router.delete("/{membership_id}")
def delete_membership(membership_id: str):
    """Remove a membership."""
    existing = MembershipRepository.get_by_id(membership_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Membership not found")

    deleted = MembershipRepository.delete(membership_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete membership")
    return {"message": "Membership deleted successfully"}
