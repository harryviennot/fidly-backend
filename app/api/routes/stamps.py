import logging

from fastapi import APIRouter, HTTPException, Depends

from app.domain.schemas import StampResponse, VoidStampRequest
from app.repositories.customer import CustomerRepository
from app.repositories.card_design import CardDesignRepository
from app.repositories.business import BusinessRepository
from app.repositories.membership import MembershipRepository
from app.repositories.transaction import TransactionRepository
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

    stamps_before = customer["stamps"]
    new_stamps = CustomerRepository.add_stamp(customer_id, max_stamps)

    # Log transaction (non-blocking)
    transaction_id = None
    try:
        txn = TransactionRepository.create(
            business_id=ctx.business_id,
            customer_id=customer_id,
            type="stamp_added",
            stamp_delta=1,
            stamps_before=stamps_before,
            stamps_after=new_stamps,
            employee_id=ctx.user["id"],
            source="scanner",
        )
        if txn:
            transaction_id = txn["id"]
    except Exception:
        logger.error("[Stamps] Failed to log stamp transaction", exc_info=True)

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
            await coordinator.on_stamp_added(
                customer=updated_customer,
                business=business,
                design=design,
            )
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
        transaction_id=transaction_id,
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
    stamps_before = customer["stamps"]
    CustomerRepository.reset_stamps(customer_id)

    # Increment total redemptions + log transaction (non-blocking)
    transaction_id = None
    try:
        CustomerRepository.increment_redemptions(customer_id)
    except Exception:
        logger.error("[Stamps] Failed to increment redemptions", exc_info=True)

    try:
        txn = TransactionRepository.create(
            business_id=ctx.business_id,
            customer_id=customer_id,
            type="reward_redeemed",
            stamp_delta=-stamps_before,
            stamps_before=stamps_before,
            stamps_after=0,
            employee_id=ctx.user["id"],
            source="scanner",
        )
        if txn:
            transaction_id = txn["id"]
    except Exception:
        logger.error("[Stamps] Failed to log redeem transaction", exc_info=True)

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
            await coordinator.on_stamp_added(
                customer=updated_customer,
                business=business,
                design=design,
            )
        except Exception as e:
            # Don't fail the redeem operation if wallet update fails
            logger.error(f"[Stamps] Wallet update error on redemption: {e}", exc_info=True)

    return StampResponse(
        customer_id=customer_id,
        name=customer["name"],
        stamps=0,
        message="Reward redeemed! Card has been reset.",
        transaction_id=transaction_id,
    )


@router.post("/{business_id}/{customer_id}/void", response_model=StampResponse)
async def void_customer_stamp(
    customer_id: str,
    body: VoidStampRequest,
    ctx: BusinessAccessContext = Depends(require_any_access),
    coordinator: PassCoordinator = Depends(get_pass_coordinator),
):
    """Void a previously added stamp.

    Requires membership in the business (any role).
    The original transaction must be stamp_added or bonus_stamp, not already voided,
    and the customer must have stamps > 0.
    """
    customer = CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if customer.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Validate original transaction
    original = TransactionRepository.get_by_id(body.transaction_id)
    if not original:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if original["business_id"] != ctx.business_id or original["customer_id"] != customer_id:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if original["type"] not in ("stamp_added", "bonus_stamp"):
        raise HTTPException(status_code=400, detail="Only stamp_added or bonus_stamp transactions can be voided")

    if TransactionRepository.is_already_voided(body.transaction_id):
        raise HTTPException(status_code=409, detail="This transaction has already been voided")

    if customer["stamps"] <= 0:
        raise HTTPException(status_code=400, detail="Customer has no stamps to void")

    # Decrement stamp
    stamps_before = customer["stamps"]
    new_stamps = CustomerRepository.void_stamp(customer_id)

    # Log void transaction
    transaction_id = None
    try:
        txn = TransactionRepository.create(
            business_id=ctx.business_id,
            customer_id=customer_id,
            type="stamp_voided",
            stamp_delta=-1,
            stamps_before=stamps_before,
            stamps_after=new_stamps,
            employee_id=ctx.user["id"],
            source="scanner",
            voided_transaction_id=body.transaction_id,
            metadata={"void_reason": body.reason},
        )
        if txn:
            transaction_id = txn["id"]
    except Exception:
        logger.error("[Stamps] Failed to log void transaction", exc_info=True)

    # Update wallets
    design = CardDesignRepository.get_active(ctx.business_id)
    business = BusinessRepository.get_by_id(ctx.business_id)
    updated_customer = {**customer, "stamps": new_stamps}

    if business and design:
        try:
            await coordinator.on_stamp_added(
                customer=updated_customer,
                business=business,
                design=design,
            )
        except Exception as e:
            logger.error(f"[Stamps] Wallet update error on void: {e}", exc_info=True)

    return StampResponse(
        customer_id=customer_id,
        name=customer["name"],
        stamps=new_stamps,
        message="Stamp voided.",
        transaction_id=transaction_id,
    )
