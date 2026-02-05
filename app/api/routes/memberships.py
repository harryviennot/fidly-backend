from fastapi import APIRouter, HTTPException, Depends

from app.domain.schemas import MembershipCreate, MembershipUpdate, MembershipResponse
from app.repositories.membership import MembershipRepository
from app.repositories.user import UserRepository
from app.repositories.business import BusinessRepository
from app.core.permissions import get_current_user_profile

router = APIRouter()


@router.post("", response_model=MembershipResponse)
def create_membership(
    data: MembershipCreate,
    caller: dict = Depends(get_current_user_profile),
):
    """Create a membership. Caller must be an owner or admin of the target business."""
    # Verify caller has owner/admin access to the target business
    caller_membership = MembershipRepository.get_membership(caller["id"], data.business_id)
    if not caller_membership or caller_membership["role"] not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owners and admins can add members")

    # Verify target user exists
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
def get_user_memberships(
    user_id: str,
    caller: dict = Depends(get_current_user_profile),
):
    """Get all memberships for a user. Can only query your own memberships."""
    if caller["id"] != user_id:
        raise HTTPException(status_code=403, detail="You can only view your own memberships")

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
def get_business_members(
    business_id: str,
    caller: dict = Depends(get_current_user_profile),
):
    """Get all members of a business. Caller must be a member."""
    caller_membership = MembershipRepository.get_membership(caller["id"], business_id)
    if not caller_membership:
        raise HTTPException(status_code=403, detail="You don't have access to this business")

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
def get_membership(
    membership_id: str,
    caller: dict = Depends(get_current_user_profile),
):
    """Get a specific membership. Caller must own this membership or be in the same business."""
    membership = MembershipRepository.get_by_id(membership_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    # Allow if it's your own membership or you're in the same business
    if membership["user_id"] != caller["id"]:
        caller_membership = MembershipRepository.get_membership(caller["id"], membership["business_id"])
        if not caller_membership:
            raise HTTPException(status_code=403, detail="You don't have access to this membership")

    return MembershipResponse(**membership)


@router.put("/{membership_id}", response_model=MembershipResponse)
def update_membership_role(
    membership_id: str,
    data: MembershipUpdate,
    caller: dict = Depends(get_current_user_profile),
):
    """Update a member's role. Caller must be an owner of the business."""
    existing = MembershipRepository.get_by_id(membership_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Membership not found")

    # Must be an owner of the business to change roles
    caller_membership = MembershipRepository.get_membership(caller["id"], existing["business_id"])
    if not caller_membership or caller_membership["role"] != "owner":
        raise HTTPException(status_code=403, detail="Only owners can change member roles")

    membership = MembershipRepository.update_role(membership_id, data.role)
    if not membership:
        raise HTTPException(status_code=500, detail="Failed to update membership")
    return MembershipResponse(**membership)


@router.delete("/{membership_id}")
def delete_membership(
    membership_id: str,
    caller: dict = Depends(get_current_user_profile),
):
    """Remove a membership. Caller must be an owner of the business or removing themselves."""
    existing = MembershipRepository.get_by_id(membership_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Membership not found")

    # Allow self-removal or owner removal
    is_self = existing["user_id"] == caller["id"]
    if not is_self:
        caller_membership = MembershipRepository.get_membership(caller["id"], existing["business_id"])
        if not caller_membership or caller_membership["role"] != "owner":
            raise HTTPException(status_code=403, detail="Only owners can remove other members")

    deleted = MembershipRepository.delete(membership_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete membership")
    return {"message": "Membership deleted successfully"}
