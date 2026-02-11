from fastapi import APIRouter, HTTPException, Depends

from app.domain.schemas import CustomerResponse
from app.repositories.customer import CustomerRepository
from app.core.permissions import require_management_access, BusinessAccessContext

router = APIRouter()


@router.get("/{business_id}", response_model=list[CustomerResponse])
def list_customers(
    ctx: BusinessAccessContext = Depends(require_management_access),
):
    """Get all customers for a business (requires owner or admin role)."""
    customers = CustomerRepository.get_all(ctx.business_id)
    return [CustomerResponse(**c) for c in customers]


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
