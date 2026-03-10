"""API routes for loyalty program management."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks

from app.repositories.program import ProgramRepository
from app.repositories.business import BusinessRepository
from app.repositories.card_design import CardDesignRepository
from app.services.wallets import create_pass_coordinator
from app.core.permissions import require_management_access, require_owner_access, BusinessAccessContext
from app.core.features import has_feature

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{business_id}")
def list_programs(
    ctx: BusinessAccessContext = Depends(require_management_access),
):
    """List all loyalty programs for a business.

    Auto-creates a default stamp program if none exist (lazy init for
    businesses created before the programs feature was added).
    """
    programs = ProgramRepository.list_by_business(ctx.business_id)
    if not programs:
        business = BusinessRepository.get_by_id(ctx.business_id)
        name = business.get("name", "Loyalty Program") if business else "Loyalty Program"
        program = ProgramRepository.create(
            business_id=ctx.business_id,
            name=name,
            type="stamp",
            is_active=True,
            is_default=True,
            config={"total_stamps": 10},
        )
        if program:
            programs = [program]
    return programs


@router.post("/{business_id}")
def create_program(
    body: dict,
    ctx: BusinessAccessContext = Depends(require_owner_access),
):
    """Create a new loyalty program."""
    business = BusinessRepository.get_by_id(ctx.business_id)
    tier = business.get("subscription_tier", "pay") if business else "pay"

    # Check if business can have multiple programs
    if not has_feature(tier, "multiple_programs"):
        existing = ProgramRepository.get_active(ctx.business_id)
        if len(existing) >= 1:
            raise HTTPException(
                status_code=403,
                detail="Upgrade to Pro to create multiple programs",
            )

    program = ProgramRepository.create(
        business_id=ctx.business_id,
        name=body.get("name", "Loyalty Program"),
        type=body.get("type", "stamp"),
        is_active=body.get("is_active", True),
        is_default=body.get("is_default", False),
        config=body.get("config", {}),
        reward_name=body.get("reward_name"),
        reward_description=body.get("reward_description"),
        back_fields=body.get("back_fields"),
        translations=body.get("translations"),
    )
    if not program:
        raise HTTPException(status_code=500, detail="Failed to create program")
    return program


@router.get("/{business_id}/{program_id}")
def get_program(
    program_id: str,
    ctx: BusinessAccessContext = Depends(require_management_access),
):
    """Get a specific program."""
    program = ProgramRepository.get_by_id(program_id)
    if not program or program.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Program not found")
    return program


@router.patch("/{business_id}/{program_id}")
def update_program(
    program_id: str,
    body: dict,
    background_tasks: BackgroundTasks,
    ctx: BusinessAccessContext = Depends(require_owner_access),
):
    """Update a program."""
    program = ProgramRepository.get_by_id(program_id)
    if not program or program.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Program not found")

    # Filter allowed fields
    allowed = {"name", "type", "is_active", "config", "reward_name", "reward_description", "back_fields", "translations"}
    updates = {k: v for k, v in body.items() if k in allowed}

    if not updates:
        return program

    # Detect total_stamps change
    old_config = program.get("config", {})
    if isinstance(old_config, str):
        import json
        old_config = json.loads(old_config)
    old_total = old_config.get("total_stamps", 10)

    new_config = updates.get("config")
    new_total = new_config.get("total_stamps", old_total) if new_config else old_total
    stamps_changed = new_total != old_total

    updated = ProgramRepository.update(program_id, **updates)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update program")

    # If total_stamps changed, sync to all designs and regenerate strips for active design
    if stamps_changed:
        designs = CardDesignRepository.get_all(ctx.business_id)
        for d in designs:
            CardDesignRepository.update(d["id"], total_stamps=new_total)

        active_design = CardDesignRepository.get_active(ctx.business_id)
        if active_design:
            active_design["total_stamps"] = new_total
            business = BusinessRepository.get_by_id(ctx.business_id)
            coordinator = create_pass_coordinator()

            async def regen_and_notify():
                try:
                    await coordinator.on_design_updated(
                        business=business,
                        design=active_design,
                        regenerate_strips=True,
                    )
                except Exception as e:
                    logger.error(f"Strip regeneration after stamps change: {e}")

            background_tasks.add_task(regen_and_notify)

    return updated


@router.post("/{business_id}/{program_id}/activate")
def activate_program(
    program_id: str,
    ctx: BusinessAccessContext = Depends(require_owner_access),
):
    """Activate a program."""
    program = ProgramRepository.get_by_id(program_id)
    if not program or program.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Program not found")

    updated = ProgramRepository.activate(program_id)
    return updated


@router.post("/{business_id}/{program_id}/deactivate")
def deactivate_program(
    program_id: str,
    ctx: BusinessAccessContext = Depends(require_owner_access),
):
    """Deactivate a program."""
    program = ProgramRepository.get_by_id(program_id)
    if not program or program.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Program not found")

    if program.get("is_default"):
        raise HTTPException(status_code=400, detail="Cannot deactivate the default program")

    updated = ProgramRepository.deactivate(program_id)
    return updated
