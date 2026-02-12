from typing import Optional

from fastapi import Depends, HTTPException, status

from app.core.security import require_auth
from app.repositories.user import UserRepository
from app.repositories.membership import MembershipRepository
from app.repositories.business import BusinessRepository



def get_current_user_profile(auth_payload: dict = Depends(require_auth)) -> dict:
    """Get the public user profile from auth payload.

    Args:
        auth_payload: JWT payload from require_auth dependency

    Returns:
        User profile dict from public.users table

    Raises:
        HTTPException 404 if user profile not found
    """
    auth_id = auth_payload.get("sub")
    if not auth_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing sub claim"
        )

    user = UserRepository.get_by_id(auth_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found. Please complete registration."
        )

    return user


class BusinessAccessContext:
    """Context object containing user, membership, and business_id."""

    def __init__(self, user: dict, membership: dict, business_id: str):
        self.user = user
        self.membership = membership
        self.business_id = business_id
        self.role = membership["role"]
        self.is_owner = membership["role"] == "owner"


def require_business_access(role: Optional[str] = None):
    """Dependency factory to verify user has access to a business.

    Args:
        role: Optional required role ('owner' or 'scanner').
              If None, any role is accepted.

    Returns:
        A FastAPI dependency function that returns BusinessAccessContext

    Example:
        @router.get("/{business_id}/customers")
        def list_customers(
            business_id: str,
            ctx: BusinessAccessContext = Depends(require_business_access())
        ):
            # ctx.user, ctx.membership, ctx.business_id available
            pass

        @router.delete("/{business_id}")
        def delete_business(
            business_id: str,
            ctx: BusinessAccessContext = Depends(require_business_access("owner"))
        ):
            # Only owners can access this route
            pass
    """

    def dependency(
        business_id: str,
        user: dict = Depends(get_current_user_profile)
    ) -> BusinessAccessContext:
        membership = MembershipRepository.get_membership(user["id"], business_id)
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this business"
            )

        if role and membership["role"] != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires '{role}' role"
            )

        # Check business is active
        business = BusinessRepository.get_by_id(business_id)
        if not business or business.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your business account is pending activation. You'll receive an email when approved."
            )

        return BusinessAccessContext(
            user=user,
            membership=membership,
            business_id=business_id
        )

    return dependency


# Pre-configured dependency shortcuts
require_any_access = require_business_access()
require_owner_access = require_business_access(role="owner")
require_scanner_access = require_business_access(role="scanner")


def _require_management_access(
    business_id: str,
    user: dict = Depends(get_current_user_profile),
) -> BusinessAccessContext:
    """Allow owner and admin roles, but not scanner."""
    membership = MembershipRepository.get_membership(user["id"], business_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this business",
        )

    if membership["role"] not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires 'owner' or 'admin' role",
        )

    business = BusinessRepository.get_by_id(business_id)
    if not business or business.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your business account is pending activation. You'll receive an email when approved.",
        )

    return BusinessAccessContext(
        user=user,
        membership=membership,
        business_id=business_id,
    )


require_management_access = _require_management_access
