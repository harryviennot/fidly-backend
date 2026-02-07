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
from app.api.routes.google_wallet import pre_generate_hero_image

router = APIRouter()


def update_google_wallet_passes(customer_id: str, business_id: str, stamps: int, max_stamps: int):
    """
    Update Google Wallet passes for a customer.

    Handles notification rate limiting (3 per 24h per pass).
    This is synchronous as the Google Wallet API client uses blocking HTTP.
    """
    import time
    from app.core.config import settings

    if not is_google_wallet_configured():
        print(f"Google Wallet: Not configured, skipping update for {customer_id}")
        return

    google_object_ids = DeviceRepository.get_google_registrations(customer_id)
    print(f"Google Wallet: customer={customer_id}, stamps={stamps}, registrations={google_object_ids}")

    if not google_object_ids:
        print(f"Google Wallet: No registrations found for {customer_id}")
        return

    try:
        google_client = create_google_wallet_client()

        # Determine if we should send a notification
        should_notify = GoogleNotificationRepository.should_notify(
            customer_id, stamps, max_stamps
        )
        print(f"Google Wallet: should_notify={should_notify}")

        # Pre-generate and cache the hero image BEFORE sending update to Google
        # This ensures the image is ready when Google fetches it
        print(f"Google Wallet: Pre-generating hero image for business={business_id}, stamps={stamps}")
        pre_generate_hero_image(business_id, stamps)

        # Generate hero image URL with cache busting timestamp
        hero_url = f"{settings.base_url}/google-wallet/hero/{business_id}?stamps={stamps}&v={int(time.time())}"

        for object_id in google_object_ids:
            try:
                print(f"Google Wallet: Updating object {object_id} with stamps={stamps}")

                # Build update data for GenericObject
                update_data = {
                    "subheader": f"{stamps} / {max_stamps} stamps",
                    "text_modules_data": [
                        {
                            "id": "progress",
                            "header": "Progress",
                            "body": f"{stamps} / {max_stamps} stamps"
                        }
                    ],
                    # Per-customer hero image showing their stamp progress
                    "hero_image": {
                        "sourceUri": {
                            "uri": hero_url
                        },
                        "contentDescription": {
                            "defaultValue": {
                                "language": "en",
                                "value": f"{stamps} of {max_stamps} stamps collected"
                            }
                        }
                    }
                }

                # Add reward message if earned
                if stamps >= max_stamps:
                    update_data["messages"] = [
                        {
                            "header": "Congratulations!",
                            "body": "You've earned a reward! Show this to redeem.",
                            "id": "reward_ready"
                        }
                    ]

                try:
                    result = google_client.update_generic_object(
                        object_id,
                        update_data,
                        notify=should_notify
                    )
                    print(f"Google Wallet: Update successful for {object_id}")
                except Exception as update_error:
                    error_msg = str(update_error)

                    # If object is a legacy loyaltyObject, use legacy update
                    if "object type is not genericObject" in error_msg and "loyaltyObject" in error_msg:
                        print("Google Wallet: Legacy loyaltyObject detected, using legacy update...")
                        # Convert to legacy format (no heroImage at object level for loyalty)
                        legacy_data = {
                            "stamps": stamps,
                            "text_modules_data": update_data.get("text_modules_data", [])
                        }
                        result = google_client.update_loyalty_object(
                            object_id,
                            legacy_data,
                            notify=should_notify
                        )
                        print(f"Google Wallet: Legacy update successful for {object_id}")
                    # If hero image fails, retry without it
                    elif "Image cannot be loaded" in error_msg:
                        print("Google Wallet: Hero image failed, retrying without it...")
                        del update_data["hero_image"]
                        result = google_client.update_generic_object(
                            object_id,
                            update_data,
                            notify=should_notify
                        )
                        print(f"Google Wallet: Update successful (without hero) for {object_id}")
                    else:
                        raise update_error

                # Record notification if we sent one
                if should_notify:
                    notification_type = "reward" if stamps == max_stamps or stamps == 0 else "stamp"
                    GoogleNotificationRepository.record_notification(
                        customer_id, object_id, notification_type
                    )

            except Exception as e:
                print(f"Google Wallet: Failed to update object {object_id}: {e}")

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
    update_google_wallet_passes(customer_id, ctx.business_id, new_stamps, max_stamps)

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
    update_google_wallet_passes(customer_id, ctx.business_id, 0, max_stamps)

    return StampResponse(
        customer_id=customer_id,
        name=customer["name"],
        stamps=0,
        message="Reward redeemed! Card has been reset.",
    )
