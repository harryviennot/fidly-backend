import uuid
import secrets

from fastapi import APIRouter, HTTPException

from app.domain.schemas import CustomerCreate, CustomerResponse
from app.repositories.customer import CustomerRepository
from app.core.config import settings

router = APIRouter()


@router.post("", response_model=CustomerResponse)
async def create_new_customer(customer: CustomerCreate):
    """Create a new customer and return their info with pass URL."""
    existing = await CustomerRepository.get_by_email(customer.email)
    if existing:
        return CustomerResponse(
            id=existing["id"],
            name=existing["name"],
            email=existing["email"],
            stamps=existing["stamps"],
            pass_url=f"{settings.base_url}/passes/{existing['id']}",
        )

    customer_id = str(uuid.uuid4())
    auth_token = secrets.token_hex(16)

    result = await CustomerRepository.create(customer_id, customer.name, customer.email, auth_token)

    return CustomerResponse(
        id=result["id"],
        name=result["name"],
        email=result["email"],
        stamps=result["stamps"],
        pass_url=f"{settings.base_url}/passes/{result['id']}",
    )


@router.get("", response_model=list[CustomerResponse])
async def list_customers():
    """Get all customers."""
    customers = await CustomerRepository.get_all()
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


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer_info(customer_id: str):
    """Get customer details."""
    customer = await CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return CustomerResponse(
        id=customer["id"],
        name=customer["name"],
        email=customer["email"],
        stamps=customer["stamps"],
        pass_url=f"{settings.base_url}/passes/{customer['id']}",
    )
