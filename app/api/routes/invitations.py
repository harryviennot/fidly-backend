from fastapi import APIRouter, HTTPException, Depends, status

from app.domain.schemas import (
    InvitationCreate,
    InvitationResponse,
    InvitationPublicResponse,
    UserResponse,
)
from app.repositories.invitation import InvitationRepository
from app.repositories.membership import MembershipRepository
from app.repositories.user import UserRepository
from app.repositories.business import BusinessRepository
from app.core.permissions import (
    get_current_user_profile,
    require_business_access,
    BusinessAccessContext,
)
from app.core.features import get_plan_limits
from app.core.entitlements import LimitExceededError
from app.services.email import get_email_service

router = APIRouter()


def _check_invite_permission(ctx: BusinessAccessContext, role_to_invite: str) -> None:
    """Check if the user can invite someone with the given role.

    Raises HTTPException if not allowed.
    """
    # Cannot invite owners (only admin/scanner allowed)
    if role_to_invite == "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot invite owners. There can only be one owner per business."
        )

    # Owners can invite admins and scanners
    if ctx.role == "owner":
        return

    # Admins can only invite scanners
    if ctx.role == "admin":
        if role_to_invite != "scanner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins can only invite scanners"
            )
        return

    # Scanners cannot invite anyone
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have permission to invite team members"
    )


@router.post("/{business_id}", response_model=InvitationResponse)
def create_invitation(
    business_id: str,
    data: InvitationCreate,
    ctx: BusinessAccessContext = Depends(require_business_access())
):
    """Create a new invitation and send email."""
    # Check permission to invite this role
    _check_invite_permission(ctx, data.role)

    # Check scanner limit if inviting a scanner
    if data.role == "scanner":
        business = BusinessRepository.get_by_id(business_id)
        if business:
            limits = get_plan_limits(business["subscription_tier"])
            max_scanners = limits["max_scanner_accounts"]
            if max_scanners is not None:
                # Count existing scanners + pending scanner invitations
                current_scanners = MembershipRepository.count_by_role(business_id, "scanner")
                pending_scanner_invites = InvitationRepository.count_pending_by_role(business_id, "scanner")
                total = current_scanners + pending_scanner_invites
                if total >= max_scanners:
                    raise LimitExceededError("scanner accounts", max_scanners, total)

    # Normalize email
    email = data.email.lower()

    # Check for existing pending invitation
    existing_invitation = InvitationRepository.get_pending_by_email(email, business_id)
    if existing_invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An invitation is already pending for this email"
        )

    # Check if user already a member
    user = UserRepository.get_by_email(email)
    if user:
        membership = MembershipRepository.get_membership(user["id"], business_id)
        if membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This user is already a member of this business"
            )

    # Create invitation
    invitation = InvitationRepository.create(
        business_id=business_id,
        email=email,
        name=data.name,
        role=data.role,
        invited_by=ctx.user["id"]
    )

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create invitation"
        )

    # Send email
    business = BusinessRepository.get_by_id(business_id)
    email_service = get_email_service()

    try:
        email_service.send_invitation(
            to=email,
            invitee_name=data.name,
            inviter_name=ctx.user["name"],
            business_name=business["name"],
            role=data.role,
            token=invitation["token"]
        )
    except Exception as e:
        # Log error but don't fail - invitation is created
        # Could add email_sent flag to track delivery status
        pass

    # Build response with inviter info
    invitation["inviter"] = UserResponse(
        id=ctx.user["id"],
        email=ctx.user["email"],
        name=ctx.user["name"]
    )

    return InvitationResponse(**invitation)


@router.get("/{business_id}", response_model=list[InvitationResponse])
def list_pending_invitations(
    business_id: str,
    ctx: BusinessAccessContext = Depends(require_business_access())
):
    """List all pending invitations for a business."""
    # Scanners cannot view invitations
    if ctx.role == "scanner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scanners cannot view invitations"
        )

    invitations = InvitationRepository.get_pending_for_business(business_id)

    result = []
    for inv in invitations:
        # Extract nested user data for inviter
        inviter_data = inv.pop("users", None)
        if inviter_data:
            inv["inviter"] = UserResponse(**inviter_data)
        result.append(InvitationResponse(**inv))

    return result


@router.get("/token/{token}", response_model=InvitationPublicResponse)
def get_invitation_by_token(token: str):
    """Get invitation details by token (public endpoint for acceptance page)."""
    invitation = InvitationRepository.get_by_token(token)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found"
        )

    is_expired = InvitationRepository.is_expired(invitation)

    # Extract business and inviter names from nested data
    business_data = invitation.get("businesses", {})
    inviter_data = invitation.get("users", {})

    return InvitationPublicResponse(
        id=invitation["id"],
        email=invitation["email"],
        name=invitation.get("name"),
        role=invitation["role"],
        status=invitation["status"],
        expires_at=invitation["expires_at"],
        business_name=business_data.get("name", "Unknown Business"),
        inviter_name=inviter_data.get("name", "Unknown"),
        is_expired=is_expired
    )


@router.post("/token/{token}/accept")
def accept_invitation(
    token: str,
    user: dict = Depends(get_current_user_profile)
):
    """Accept an invitation (requires authentication)."""
    invitation = InvitationRepository.get_by_token(token)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found"
        )

    # Validate invitation status
    if invitation["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invitation has already been {invitation['status']}"
        )

    # Check expiry
    if InvitationRepository.is_expired(invitation):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation has expired"
        )

    # Email must match exactly
    if user["email"].lower() != invitation["email"].lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invitation was sent to a different email address"
        )

    # Check not already a member
    existing_membership = MembershipRepository.get_membership(
        user["id"],
        invitation["business_id"]
    )
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a member of this business"
        )

    # Create membership
    membership = MembershipRepository.create(
        user_id=user["id"],
        business_id=invitation["business_id"],
        role=invitation["role"],
        invited_by=invitation["invited_by"]
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create membership"
        )

    # Mark invitation as accepted
    InvitationRepository.mark_accepted(invitation["id"])

    # Get business name for response
    business_data = invitation.get("businesses", {})

    return {
        "message": "Invitation accepted successfully",
        "business_id": invitation["business_id"],
        "business_name": business_data.get("name", ""),
        "role": invitation["role"]
    }


@router.post("/{business_id}/{invitation_id}/resend")
def resend_invitation(
    business_id: str,
    invitation_id: str,
    ctx: BusinessAccessContext = Depends(require_business_access())
):
    """Resend invitation email."""
    # Scanners cannot resend invitations
    if ctx.role == "scanner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scanners cannot resend invitations"
        )

    invitation = InvitationRepository.get_by_id(invitation_id)

    if not invitation or invitation["business_id"] != business_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found"
        )

    if invitation["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only resend pending invitations"
        )

    business = BusinessRepository.get_by_id(business_id)
    email_service = get_email_service()

    try:
        email_service.send_invitation(
            to=invitation["email"],
            invitee_name=invitation.get("name"),
            inviter_name=ctx.user["name"],
            business_name=business["name"],
            role=invitation["role"],
            token=invitation["token"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send email"
        )

    return {"message": "Invitation email resent"}


@router.delete("/{business_id}/{invitation_id}")
def cancel_invitation(
    business_id: str,
    invitation_id: str,
    ctx: BusinessAccessContext = Depends(require_business_access())
):
    """Cancel/delete a pending invitation."""
    # Scanners cannot cancel invitations
    if ctx.role == "scanner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scanners cannot cancel invitations"
        )

    invitation = InvitationRepository.get_by_id(invitation_id)

    if not invitation or invitation["business_id"] != business_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found"
        )

    deleted = InvitationRepository.delete(invitation_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete invitation"
        )

    return {"message": "Invitation cancelled"}
