from fastapi import APIRouter, HTTPException, Depends

from app.domain.schemas import StampResponse
from app.repositories.customer import CustomerRepository
from app.repositories.card_design import CardDesignRepository
from app.repositories.device import DeviceRepository
from app.repositories.membership import MembershipRepository
from app.repositories.google_wallet import GoogleNotificationRepository
from app.services.apns import APNsClient
from app.services.google_wallet import create_google_wallet_client, is_google_wallet_configured
from app.api.deps import get_apns_client
from app.core.permissions import require_any_access, BusinessAccessContext

router = APIRouter()


def update_google_wallet_passes(customer_id: str, stamps: int, max_stamps: int):
    """
    Update Google Wallet passes for a customer.

    Handles notification rate limiting (3 per 24h per pass).
    This is synchronous as the Google Wallet API client uses blocking HTTP.
    """
    if not is_google_wallet_configured():
        return

    google_object_ids = DeviceRepository.get_google_registrations(customer_id)
    if not google_object_ids:
        return

    try:
        google_client = create_google_wallet_client()

        # Determine if we should send a notification
        should_notify = GoogleNotificationRepository.should_notify(
            customer_id, stamps, max_stamps
        )

        for object_id in google_object_ids:
            try:
                google_client.update_loyalty_object(
                    object_id,
                    {"stamps": stamps},
                    notify=should_notify
                )

                # Record notification if we sent one
                if should_notify:
                    notification_type = "reward" if stamps == max_stamps or stamps == 0 else "stamp"
                    GoogleNotificationRepository.record_notification(
                        customer_id, object_id, notification_type
                    )

            except Exception as e:
                print(f"Failed to update Google Wallet object {object_id}: {e}")

    except Exception as e:
        print(f"Failed to create Google Wallet client: {e}")


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

    # Send Apple Wallet push notifications
    push_tokens = DeviceRepository.get_push_tokens(customer_id)
    if push_tokens:
        await apns_client.send_to_all_devices(push_tokens)

    # Update Google Wallet passes
    update_google_wallet_passes(customer_id, new_stamps, max_stamps)

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

    # Trigger Apple Wallet push notification for pass update
    push_tokens = DeviceRepository.get_push_tokens(customer_id)
    if push_tokens:
        await apns_client.send_to_all_devices(push_tokens)

    # Update Google Wallet passes (stamps reset to 0)
    update_google_wallet_passes(customer_id, 0, max_stamps)

    return StampResponse(
        customer_id=customer_id,
        name=customer["name"],
        stamps=0,
        message="Reward redeemed! Card has been reset.",
    )
