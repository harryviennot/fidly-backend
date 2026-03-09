from fastapi import APIRouter, HTTPException, Depends, Query

from app.domain.schemas import CustomerResponse, PaginatedCustomerResponse
from app.repositories.customer import CustomerRepository
from app.core.permissions import require_management_access, BusinessAccessContext

router = APIRouter()


@router.get("/{business_id}", response_model=PaginatedCustomerResponse)
def list_customers(
    ctx: BusinessAccessContext = Depends(require_management_access),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Get paginated customers for a business (requires owner or admin role)."""
    result = CustomerRepository.get_paginated(ctx.business_id, limit=limit, offset=offset)
    return PaginatedCustomerResponse(
        data=[CustomerResponse(**c) for c in result["data"]],
        total=result["total"],
        limit=limit,
        offset=offset,
    )


@router.get("/{business_id}/{customer_id}", response_model=CustomerResponse)
def get_customer_info(
    customer_id: str,
    ctx: BusinessAccessContext = Depends(require_management_access),
):
    """Get customer details (requires owner or admin role)."""
    customer = CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if customer.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    return CustomerResponse(**customer)
