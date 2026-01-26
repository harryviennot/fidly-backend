import secrets

from fastapi import APIRouter, HTTPException

from app.domain.schemas import CustomerCreate, CustomerResponse
from app.repositories.customer import CustomerRepository
from app.repositories.business import BusinessRepository
from app.core.config import settings

router = APIRouter()


@router.post("/{business_id}", response_model=CustomerResponse)
def create_new_customer(business_id: str, customer: CustomerCreate):
    """Create a new customer for a business and return their info with pass URL."""
    # Verify business exists
    business = BusinessRepository.get_by_id(business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    existing = CustomerRepository.get_by_email(business_id, customer.email)
    if existing:
        return CustomerResponse(
            id=existing["id"],
            name=existing["name"],
            email=existing["email"],
            stamps=existing["stamps"],
            pass_url=f"{settings.base_url}/passes/{existing['id']}",
        )

    auth_token = secrets.token_hex(16)

    result = CustomerRepository.create(business_id, customer.name, customer.email, auth_token)
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
def list_customers(business_id: str):
    """Get all customers for a business."""
    # Verify business exists
    business = BusinessRepository.get_by_id(business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    customers = CustomerRepository.get_all(business_id)
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
def get_customer_info(business_id: str, customer_id: str):
    """Get customer details."""
    customer = CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Verify customer belongs to the business
    if customer.get("business_id") != business_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    return CustomerResponse(
        id=customer["id"],
        name=customer["name"],
        email=customer["email"],
        stamps=customer["stamps"],
        pass_url=f"{settings.base_url}/passes/{customer['id']}",
    )
