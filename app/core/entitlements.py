"""
Entitlement checking for subscription-gated features.

Uses dependency injection pattern consistent with permissions.py.
Provides reusable dependencies for checking plan limits before operations.

Usage:
    @router.post("/{business_id}")
    def create_something(
        ctx: BusinessAccessContext = Depends(require_owner_access),
        _: BusinessAccessContext = Depends(require_can_create_design)
    ):
        # Only executes if user has permission AND plan allows it
        pass
"""
from fastapi import Depends, HTTPException, status

from app.core.features import get_plan_limits, has_feature
from app.core.permissions import BusinessAccessContext, require_any_access
from app.repositories.business import BusinessRepository
from app.repositories.card_design import CardDesignRepository
from app.repositories.membership import MembershipRepository


class LimitExceededError(HTTPException):
    """Raised when a plan limit would be exceeded by an operation."""

    def __init__(self, resource: str, limit: int, current: int):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "LIMIT_EXCEEDED",
                "resource": resource,
                "limit": limit,
                "current": current,
                "message": f"Your plan allows {limit} {resource}. You currently have {current}.",
                "upgrade_required": True,
            }
        )


class FeatureNotAvailableError(HTTPException):
    """Raised when a feature is not available in the user's plan."""

    def __init__(self, feature: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FEATURE_NOT_AVAILABLE",
                "feature": feature,
                "message": f"The '{feature}' feature requires a Pro subscription.",
                "upgrade_required": True,
            }
        )


def require_can_create_design(
    ctx: BusinessAccessContext = Depends(require_any_access)
) -> BusinessAccessContext:
    """Dependency that checks if the business can create another design.

    NOTE: Tier limits temporarily bypassed for MVP.

    Raises:
        LimitExceededError: If design limit would be exceeded

    Returns:
        The BusinessAccessContext for chaining
    """
    # BYPASSED FOR MVP: Re-enable when implementing paid tiers
    # Original limit checking code preserved below:
    # business = BusinessRepository.get_by_id(ctx.business_id)
    # if not business:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail="Business not found"
    #     )
    # limits = get_plan_limits(business["subscription_tier"])
    # max_designs = limits["max_card_designs"]
    # if max_designs is not None:
    #     current = CardDesignRepository.count(ctx.business_id)
    #     if current >= max_designs:
    #         raise LimitExceededError("card designs", max_designs, current)
    return ctx


def require_can_add_scanner(
    ctx: BusinessAccessContext = Depends(require_any_access)
) -> BusinessAccessContext:
    """Dependency that checks if the business can add another scanner.

    NOTE: Tier limits temporarily bypassed for MVP.

    Raises:
        LimitExceededError: If scanner account limit would be exceeded

    Returns:
        The BusinessAccessContext for chaining
    """
    # BYPASSED FOR MVP: Re-enable when implementing paid tiers
    # Original limit checking code preserved below:
    # business = BusinessRepository.get_by_id(ctx.business_id)
    # if not business:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail="Business not found"
    #     )
    # limits = get_plan_limits(business["subscription_tier"])
    # max_scanners = limits["max_scanner_accounts"]
    # if max_scanners is not None:
    #     current = MembershipRepository.count_by_role(ctx.business_id, "scanner")
    #     if current >= max_scanners:
    #         raise LimitExceededError("scanner accounts", max_scanners, current)
    return ctx


def require_can_add_team_member(
    ctx: BusinessAccessContext = Depends(require_any_access)
) -> BusinessAccessContext:
    """Dependency that checks if the business can add another team member (any role).

    Note: This is separate from scanner limit - some plans may have different
    limits for total team members vs scanners specifically.

    Currently not enforced (no max_team_members limit defined), but available
    for future use.

    Returns:
        The BusinessAccessContext for chaining
    """
    # Currently no total team member limit, but structure ready for future use
    return ctx


def require_feature(feature: str):
    """Factory to create a dependency that requires a specific feature.

    Args:
        feature: The feature name to require (e.g., 'geofencing', 'scheduled_campaigns')

    Returns:
        A FastAPI dependency function

    Usage:
        @router.post("/{business_id}/schedule")
        def schedule_campaign(
            ctx: BusinessAccessContext = Depends(require_feature("scheduled_campaigns"))
        ):
            pass
    """
    def dependency(
        ctx: BusinessAccessContext = Depends(require_any_access)
    ) -> BusinessAccessContext:
        business = BusinessRepository.get_by_id(ctx.business_id)
        if not business:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business not found"
            )

        if not has_feature(business["subscription_tier"], feature):
            raise FeatureNotAvailableError(feature)

        return ctx

    return dependency


def get_business_usage(business_id: str) -> dict:
    """Get current resource usage for a business.

    Useful for displaying usage stats in the dashboard.

    Args:
        business_id: The business to check

    Returns:
        Dict with current usage counts
    """
    return {
        "card_designs": CardDesignRepository.count(business_id),
        "scanner_accounts": MembershipRepository.count_by_role(business_id, "scanner"),
        "total_team_members": MembershipRepository.count(business_id),
    }


def get_business_limits_and_usage(business_id: str) -> dict:
    """Get both limits and current usage for a business.

    Useful for the settings/billing page to show usage vs limits.

    Args:
        business_id: The business to check

    Returns:
        Dict with tier, limits, and current usage
    """
    business = BusinessRepository.get_by_id(business_id)
    if not business:
        return {}

    tier = business["subscription_tier"]
    limits = get_plan_limits(tier)
    usage = get_business_usage(business_id)

    return {
        "tier": tier,
        "limits": limits,
        "usage": usage,
    }
