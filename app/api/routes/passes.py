from fastapi import APIRouter, HTTPException, Response

from app.repositories.customer import CustomerRepository
from app.services.pass_generator import create_pass_generator_for_business, create_pass_generator

router = APIRouter()


@router.get("/{customer_id}")
def download_pass(customer_id: str):
    """Download the .pkpass file for a customer."""
    customer = CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    business_id = customer.get("business_id")

    # Use per-business certs when business_id is available
    if business_id:
        pass_generator = create_pass_generator_for_business(business_id)
    else:
        pass_generator = create_pass_generator()

    pass_data = pass_generator.generate_pass(
        customer_id=customer["id"],
        name=customer["name"],
        stamps=customer["stamps"],
        auth_token=customer["auth_token"],
        business_id=business_id,
    )

    safe_name = customer["name"].encode("ascii", "ignore").decode("ascii").replace('"', "")
    if not safe_name:
        safe_name = "loyalty-card"

    return Response(
        content=pass_data,
        media_type="application/vnd.apple.pkpass",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}-loyalty.pkpass"',
        },
    )
