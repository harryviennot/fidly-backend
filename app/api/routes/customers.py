import secrets

from fastapi import APIRouter, HTTPException, Depends

from app.domain.schemas import CustomerCreate, CustomerResponse
from app.repositories.customer import CustomerRepository
from app.core.config import settings
from app.core.permissions import require_any_access, BusinessAccessContext

router = APIRouter()


@router.post("/{business_id}", response_model=CustomerResponse)
def create_new_customer(
    customer: CustomerCreate,
    ctx: BusinessAccessContext = Depends(require_any_access)
):
    """Create a new customer for a business (requires membership)."""
    existing = CustomerRepository.get_by_email(ctx.business_id, customer.email)
    if existing:
        return CustomerResponse(
            id=existing["id"],
            name=existing["name"],
            email=existing["email"],
            stamps=existing["stamps"],
            pass_url=f"{settings.base_url}/passes/{existing['id']}",
        )

    auth_token = secrets.token_hex(16)

    result = CustomerRepository.create(ctx.business_id, customer.name, customer.email, auth_token)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create customer")

    return CustomerResponse(
        id=result["id"],
        name=result["name"],
        email=result["email"],
        stamps=result["stamps"],
        pass_url=f"{settings.base_url}/passes/{result['id']}",
    )


@router.get("/{business_id}", response_model=list[CustomerResponse])
def list_customers(ctx: BusinessAccessContext = Depends(require_any_access)):
    """Get all customers for a business (requires membership)."""
    customers = CustomerRepository.get_all(ctx.business_id)
    return [
        CustomerResponse(
            id=c["id"],
            name=c["name"],
            email=c["email"],
            stamps=c["stamps"],
            pass_url=f"{settings.base_url}/passes/{c['id']}",
        )
        for c in customers
    ]


@router.get("/{business_id}/{customer_id}", response_model=CustomerResponse)
def get_customer_info(
    customer_id: str,
    ctx: BusinessAccessContext = Depends(require_any_access)
):
    """Get customer details (requires membership)."""
    customer = CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Verify customer belongs to the business
    if customer.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    return CustomerResponse(
        id=customer["id"],
        name=customer["name"],
        email=customer["email"],
        stamps=customer["stamps"],
        pass_url=f"{settings.base_url}/passes/{customer['id']}",
    )
