import logging

from fastapi import APIRouter, HTTPException, Depends

from app.domain.schemas import StampResponse
from app.repositories.customer import CustomerRepository
from app.repositories.card_design import CardDesignRepository
from app.repositories.business import BusinessRepository
from app.repositories.membership import MembershipRepository
from app.services.wallets import PassCoordinator, create_pass_coordinator
from app.core.permissions import require_any_access, BusinessAccessContext

logger = logging.getLogger(__name__)

router = APIRouter()


def get_pass_coordinator() -> PassCoordinator:
    """Dependency to get PassCoordinator."""
    return create_pass_coordinator()


@router.post("/{business_id}/{customer_id}", response_model=StampResponse)
async def add_customer_stamp(
    customer_id: str,
    ctx: BusinessAccessContext = Depends(require_any_access),
    coordinator: PassCoordinator = Depends(get_pass_coordinator),
):
    """Add a stamp to a customer and trigger push notification.

    Requires membership in the business (any role: owner or scanner).
    Updates both Apple Wallet and Google Wallet passes.
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

    # Update wallets (Apple via push, Google via API update)
    # Get business for Google Wallet updates
    business = BusinessRepository.get_by_id(ctx.business_id)

    # Update customer object with new stamp count for wallet update
    updated_customer = {**customer, "stamps": new_stamps}

    if business and design:
        try:
            logger.info(
                f"[Stamps] Triggering wallet updates for customer {customer_id}, "
                f"new_stamps={new_stamps}"
            )
            result = await coordinator.on_stamp_added(
                customer=updated_customer,
                business=business,
                design=design,
            )
            logger.info(f"[Stamps] Wallet update results: {result}")
        except Exception as e:
            # Don't fail the stamp operation if wallet update fails
            logger.error(f"[Stamps] Wallet update error: {e}", exc_info=True)

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
    coordinator: PassCoordinator = Depends(get_pass_coordinator),
):
    """Redeem a customer's reward by resetting stamps to 0.

    Requires membership in the business (any role: owner or scanner).
    Updates both Apple Wallet and Google Wallet passes.
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

    # Update wallets (Apple via push, Google via API update)
    # Get business for Google Wallet updates
    business = BusinessRepository.get_by_id(ctx.business_id)

    # Update customer object with reset stamp count for wallet update
    updated_customer = {**customer, "stamps": 0}

    if business and design:
        try:
            logger.info(
                f"[Stamps] Triggering wallet updates for redemption, customer {customer_id}"
            )
            result = await coordinator.on_stamp_added(
                customer=updated_customer,
                business=business,
                design=design,
            )
            logger.info(f"[Stamps] Wallet update results after redemption: {result}")
        except Exception as e:
            # Don't fail the redeem operation if wallet update fails
            logger.error(f"[Stamps] Wallet update error on redemption: {e}", exc_info=True)

    return StampResponse(
        customer_id=customer_id,
        name=customer["name"],
        stamps=0,
        message="Reward redeemed! Card has been reset.",
    )
