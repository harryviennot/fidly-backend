"""Superadmin-only API routes for platform administration."""

from fastapi import APIRouter, Depends

from app.core.security import require_superadmin
from app.repositories.business import BusinessRepository

router = APIRouter()


@router.get("/businesses")
def list_all_businesses(_: dict = Depends(require_superadmin)):
    """List all businesses on the platform (superadmin only)."""
    return BusinessRepository.get_all()
