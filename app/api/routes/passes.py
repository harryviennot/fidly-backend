from fastapi import APIRouter, HTTPException, Response, Depends

from app.repositories.customer import CustomerRepository
from app.services.pass_generator import PassGenerator
from app.api.deps import get_pass_generator

router = APIRouter()


@router.get("/{customer_id}")
def download_pass(
    customer_id: str,
    pass_generator: PassGenerator = Depends(get_pass_generator)
):
    """Download the .pkpass file for a customer."""
    customer = CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    pass_data = pass_generator.generate_pass(
        customer_id=customer["id"],
        name=customer["name"],
        stamps=customer["stamps"],
        auth_token=customer["auth_token"],
        business_id=customer.get("business_id"),
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
