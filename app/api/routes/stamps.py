import logging

from fastapi import APIRouter, HTTPException, Depends, Request

from app.domain.schemas import StampResponse, VoidStampRequest
from app.repositories.customer import CustomerRepository
from app.repositories.card_design import CardDesignRepository
from app.repositories.business import BusinessRepository
from app.repositories.membership import MembershipRepository
from app.repositories.transaction import TransactionRepository
from app.services.programs import ProgramService, EventModifiers
from app.services.programs.events import EventService
from app.services.wallets import PassCoordinator, create_pass_coordinator
from app.core.permissions import require_any_access, BusinessAccessContext
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


def get_pass_coordinator() -> PassCoordinator:
    """Dependency to get PassCoordinator."""
    return create_pass_coordinator()


@router.post("/{business_id}/{customer_id}", response_model=StampResponse)
@limiter.limit("60/minute")
async def add_customer_stamp(
    request: Request,
    customer_id: str,
    ctx: BusinessAccessContext = Depends(require_any_access),
    coordinator: PassCoordinator = Depends(get_pass_coordinator),
):
    """Add a stamp to a customer and trigger push notification.

    Requires membership in the business (any role: owner or scanner).
    Updates both Apple Wallet and Google Wallet passes.

    Now delegates to ProgramService for the default program.
    """
    customer = CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if customer.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Use ProgramService for stamp logic
    program_service = ProgramService()

    # Check for active promotional events
    try:
        active_events = EventService.get_active_events(ctx.business_id)
        modifiers = EventService.calculate_modifiers(active_events)
    except Exception:
        modifiers = EventModifiers()

    try:
        result = await program_service.add_progress(
            customer_id=customer_id,
            business_id=ctx.business_id,
            employee_id=ctx.user["id"],
            source="scanner",
            modifiers=modifiers,
        )
    except ValueError as e:
        # Handle "already at max stamps" case
        if "not active" in str(e).lower():
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    # Track scanner activity
    try:
        MembershipRepository.record_scan_activity(ctx.user["id"], ctx.business_id)
    except Exception:
        pass

    # Update wallets (Apple via push, Google via API update)
    business = BusinessRepository.get_by_id(ctx.business_id)
    design = CardDesignRepository.get_active(ctx.business_id)
    updated_customer = {**customer, "stamps": result.value_after}

    if business and design:
        try:
            await coordinator.on_stamp_added(
                customer=updated_customer,
                business=business,
                design=design,
            )
        except Exception as e:
            logger.error(f"[Stamps] Wallet update error: {e}", exc_info=True)

    message = "Stamp added!"
    if result.reward_earned:
        message = "Congratulations! You've earned a reward!"
    elif result.delta == 0:
        message = "Already at maximum stamps! Ready for reward."

    return StampResponse(
        customer_id=customer_id,
        name=customer["name"],
        stamps=result.value_after,
        message=message,
        transaction_id=result.transaction_id,
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

    Now delegates to ProgramService for redemption logic.
    """
    customer = CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if customer.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Use ProgramService for redemption
    program_service = ProgramService()
    program = program_service.get_default_program(ctx.business_id)
    if not program:
        raise HTTPException(status_code=500, detail="No default program configured")

    from app.repositories.enrollment import EnrollmentRepository
    enrollment = EnrollmentRepository.get_or_create(
        customer_id, program["id"], program.get("type", "stamp")
    )

    try:
        result = await program_service.redeem_reward(
            enrollment_id=enrollment["id"],
            business_id=ctx.business_id,
            employee_id=ctx.user["id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Track scanner activity
    try:
        MembershipRepository.record_scan_activity(ctx.user["id"], ctx.business_id)
    except Exception:
        pass

    # Update wallets
    business = BusinessRepository.get_by_id(ctx.business_id)
    design = CardDesignRepository.get_active(ctx.business_id)
    updated_customer = {**customer, "stamps": result.value_after}

    if business and design:
        try:
            await coordinator.on_stamp_added(
                customer=updated_customer,
                business=business,
                design=design,
            )
        except Exception as e:
            logger.error(f"[Stamps] Wallet update error on redemption: {e}", exc_info=True)

    return StampResponse(
        customer_id=customer_id,
        name=customer["name"],
        stamps=result.value_after,
        message="Reward redeemed! Card has been reset.",
        transaction_id=result.transaction_id,
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

    # Resolve enrollment for this customer's default program
    from app.repositories.enrollment import EnrollmentRepository
    program_service = ProgramService()
    program = program_service.get_default_program(ctx.business_id)
    if not program:
        raise HTTPException(status_code=500, detail="No default program configured")

    enrollment = EnrollmentRepository.get_by_customer_and_program(customer_id, program["id"])
    if not enrollment:
        raise HTTPException(status_code=400, detail="Customer has no enrollment to void")

    stamps_before = enrollment.get("progress", {}).get("stamps", 0)
    if stamps_before <= 0:
        raise HTTPException(status_code=400, detail="Customer has no stamps to void")

    # Atomic decrement via RPC
    new_stamps = EnrollmentRepository.void_stamp(enrollment["id"])

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
