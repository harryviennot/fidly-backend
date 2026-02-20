"""API routes for enrollment management."""

import logging

from fastapi import APIRouter, HTTPException, Depends

from app.repositories.enrollment import EnrollmentRepository
from app.repositories.program import ProgramRepository
from app.core.permissions import require_any_access, BusinessAccessContext

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{business_id}/{customer_id}")
def get_customer_enrollments(
    customer_id: str,
    ctx: BusinessAccessContext = Depends(require_any_access),
):
    """Get all enrollments for a customer."""
    enrollments = EnrollmentRepository.get_customer_enrollments(customer_id)
    return enrollments


@router.post("/{business_id}")
def enroll_customer(
    body: dict,
    ctx: BusinessAccessContext = Depends(require_any_access),
):
    """Manually enroll a customer in a program."""
    customer_id = body.get("customer_id")
    program_id = body.get("program_id")

    if not customer_id or not program_id:
        raise HTTPException(status_code=400, detail="customer_id and program_id are required")

    program = ProgramRepository.get_by_id(program_id)
    if not program or program.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Program not found")

    enrollment = EnrollmentRepository.get_or_create(
        customer_id=customer_id,
        program_id=program_id,
        program_type=program.get("type", "stamp"),
    )
    return enrollment
