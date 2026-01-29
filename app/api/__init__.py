from fastapi import APIRouter

from .routes import (
    businesses,
    customers,
    designs,
    health,
    invitations,
    memberships,
    onboarding,
    passes,
    stamps,
    users,
    wallet,
)

api_router = APIRouter()

# Health check
api_router.include_router(health.router, tags=["health"])

# Onboarding
api_router.include_router(onboarding.router, prefix="/onboarding/progress", tags=["onboarding"])

# Multi-tenant management
api_router.include_router(businesses.router, prefix="/businesses", tags=["businesses"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(memberships.router, prefix="/memberships", tags=["memberships"])
api_router.include_router(invitations.router, prefix="/invitations", tags=["invitations"])

# Business-scoped resources
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(designs.router, prefix="/designs", tags=["designs"])

# Customer-facing endpoints
api_router.include_router(passes.router, prefix="/passes", tags=["passes"])
api_router.include_router(stamps.router, prefix="/stamps", tags=["stamps"])
api_router.include_router(wallet.router, prefix="/wallet", tags=["wallet"])
