from fastapi import APIRouter, HTTPException, Depends

from app.domain.schemas import StampResponse
from app.repositories.customer import CustomerRepository
from app.repositories.card_design import CardDesignRepository
from app.repositories.device import DeviceRepository
from app.repositories.membership import MembershipRepository
from app.services.apns import APNsClient
from app.api.deps import get_apns_client
from app.core.permissions import require_any_access, BusinessAccessContext

router = APIRouter()


@router.post("/{business_id}/{customer_id}", response_model=StampResponse)
async def add_customer_stamp(
    customer_id: str,
    ctx: BusinessAccessContext = Depends(require_any_access),
    apns_client: APNsClient = Depends(get_apns_client),
):
    """Add a stamp to a customer and trigger push notification.

    Requires membership in the business (any role: owner or scanner).
    """
    customer = CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Verify customer belongs to the authenticated business
    if customer.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get max stamps from active design for this business
    max_stamps = 10
    design = CardDesignRepository.get_active(ctx.business_id)
    if design:
        max_stamps = design.get("total_stamps", 10)

    if customer["stamps"] >= max_stamps:
        return StampResponse(
            customer_id=customer_id,
            name=customer["name"],
            stamps=max_stamps,
            message="Already at maximum stamps! Ready for reward.",
        )

    new_stamps = CustomerRepository.add_stamp(customer_id, max_stamps)

    # Track scanner activity using authenticated user
    try:
        MembershipRepository.record_scan_activity(ctx.user["id"], ctx.business_id)
    except Exception:
        # Don't fail the stamp operation if activity tracking fails
        pass

    push_tokens = DeviceRepository.get_push_tokens(customer_id)
    if push_tokens:
        await apns_client.send_to_all_devices(push_tokens)

    message = "Stamp added!"
    if new_stamps == max_stamps:
        message = "Congratulations! You've earned a reward!"

    return StampResponse(
        customer_id=customer_id,
        name=customer["name"],
        stamps=new_stamps,
        message=message,
    )


@router.post("/{business_id}/{customer_id}/redeem", response_model=StampResponse)
async def redeem_customer_reward(
    customer_id: str,
    ctx: BusinessAccessContext = Depends(require_any_access),
    apns_client: APNsClient = Depends(get_apns_client),
):
    """Redeem a customer's reward by resetting stamps to 0.

    Requires membership in the business (any role: owner or scanner).
    """
    customer = CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Verify customer belongs to the authenticated business
    if customer.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get max stamps from active design for this business
    max_stamps = 10
    design = CardDesignRepository.get_active(ctx.business_id)
    if design:
        max_stamps = design.get("total_stamps", 10)

    # Check if customer is eligible for reward
    if customer["stamps"] < max_stamps:
        raise HTTPException(
            status_code=400,
            detail=f"Customer only has {customer['stamps']}/{max_stamps} stamps. Not eligible for reward yet.",
        )

    # Reset stamps to 0
    CustomerRepository.reset_stamps(customer_id)

    # Track scanner activity using authenticated user
    try:
        MembershipRepository.record_scan_activity(ctx.user["id"], ctx.business_id)
    except Exception:
        # Don't fail the redeem operation if activity tracking fails
        pass

    # Trigger push notification for pass update
    push_tokens = DeviceRepository.get_push_tokens(customer_id)
    if push_tokens:
        await apns_client.send_to_all_devices(push_tokens)

    return StampResponse(
        customer_id=customer_id,
        name=customer["name"],
        stamps=0,
        message="Reward redeemed! Card has been reset.",
    )
