"""
Feature definitions and plan limits.
Single source of truth for subscription entitlements.

This module defines what each subscription tier can access:
- Usage limits (max designs, max scanners)
- Feature flags (scheduling, geofencing, etc.)

The frontend mirrors these definitions in web/src/lib/features.ts
"""
from enum import Enum
from typing import TypedDict


class SubscriptionTier(str, Enum):
    """Subscription tier identifiers."""
    PAY = "pay"
    PRO = "pro"


class PlanLimits(TypedDict):
    """Type definition for plan limit configuration."""
    max_card_designs: int | None  # None = unlimited
    max_scanner_accounts: int | None  # None = unlimited
    features: list[str]  # Feature flags enabled for this tier


# Plan configuration - edit here to change limits
PLAN_LIMITS: dict[SubscriptionTier, PlanLimits] = {
    SubscriptionTier.PAY: {
        "max_card_designs": 1,
        "max_scanner_accounts": 3,
        "features": [
            "basic_analytics",
            "standard_notifications",
        ]
    },
    SubscriptionTier.PRO: {
        "max_card_designs": None,  # unlimited
        "max_scanner_accounts": None,  # unlimited
        "features": [
            "basic_analytics",
            "advanced_analytics",
            "standard_notifications",
            "custom_notifications",
            "scheduled_campaigns",
            "multiple_locations",
            "geofencing",
            "promotional_messaging",
        ]
    }
}


def get_plan_limits(tier: str) -> PlanLimits:
    """Get limits for a subscription tier.

    Args:
        tier: The subscription tier string ('pay' or 'pro')

    Returns:
        PlanLimits dict for the tier, defaults to PAY if unknown
    """
    try:
        return PLAN_LIMITS[SubscriptionTier(tier)]
    except (ValueError, KeyError):
        return PLAN_LIMITS[SubscriptionTier.PAY]


def has_feature(tier: str, feature: str) -> bool:
    """Check if a tier has access to a specific feature.

    Args:
        tier: The subscription tier string
        feature: The feature flag name to check

    Returns:
        True if the feature is available in the tier
    """
    limits = get_plan_limits(tier)
    return feature in limits["features"]


def get_limit(tier: str, limit_name: str) -> int | None:
    """Get a specific limit value for a tier.

    Args:
        tier: The subscription tier string
        limit_name: The limit key (e.g., 'max_card_designs')

    Returns:
        The limit value, or None if unlimited
    """
    limits = get_plan_limits(tier)
    return limits.get(limit_name)
