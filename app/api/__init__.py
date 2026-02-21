from fastapi import APIRouter

from .routes import (
    admin,
    businesses,
    customers,
    demo,
    designs,
    enrollments,
    events,
    google_wallet,
    health,
    invitations,
    locations,
    memberships,
    onboarding,
    pass_type_ids,
    passes,
    profile,
    programs,
    public,
    stamps,
    sync,
    transactions,
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
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])

# Business-scoped resources
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(designs.router, prefix="/designs", tags=["designs"])

# Customer-facing endpoints
api_router.include_router(passes.router, prefix="/passes", tags=["passes"])
api_router.include_router(stamps.router, prefix="/stamps", tags=["stamps"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(wallet.router, prefix="/wallet", tags=["wallet"])
api_router.include_router(google_wallet.router, prefix="/google-wallet", tags=["google-wallet"])

# Public endpoints (no auth required)
api_router.include_router(public.router, prefix="/public", tags=["public"])

# Demo endpoints (interactive landing page demo)
api_router.include_router(demo.router, prefix="/demo", tags=["demo"])

# Loyalty programs (v2 architecture)
api_router.include_router(programs.router, prefix="/programs", tags=["programs"])
api_router.include_router(enrollments.router, prefix="/enrollments", tags=["enrollments"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(locations.router, prefix="/locations", tags=["locations"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])

# Admin: certificate pool management
api_router.include_router(pass_type_ids.router, prefix="/pass-type-ids", tags=["pass-type-ids"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
