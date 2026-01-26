from fastapi import APIRouter, HTTPException, Depends

from app.domain.schemas import StampResponse
from app.repositories.customer import CustomerRepository
from app.repositories.device import DeviceRepository
from app.services.apns import APNsClient
from app.api.deps import get_apns_client

router = APIRouter()


@router.post("/{customer_id}", response_model=StampResponse)
async def add_customer_stamp(
    customer_id: str,
    apns_client: APNsClient = Depends(get_apns_client)
):
    """Add a stamp to a customer and trigger push notification."""
    customer = await CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if customer["stamps"] >= 10:
        return StampResponse(
            customer_id=customer_id,
            name=customer["name"],
            stamps=10,
            message="Already at maximum stamps! Ready for reward.",
        )

    new_stamps = await CustomerRepository.add_stamp(customer_id)

    push_tokens = await DeviceRepository.get_push_tokens(customer_id)
    if push_tokens:
        await apns_client.send_to_all_devices(push_tokens)

    message = "Stamp added!"
    if new_stamps == 10:
        message = "Congratulations! You've earned a free coffee!"

    return StampResponse(
        customer_id=customer_id,
        name=customer["name"],
        stamps=new_stamps,
        message=message,
    )
