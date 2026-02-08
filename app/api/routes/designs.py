import asyncio
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, BackgroundTasks

from app.domain.schemas import (
    CardDesignCreate,
    CardDesignUpdate,
    CardDesignResponse,
    UploadResponse,
)
from app.repositories.card_design import CardDesignRepository
from app.repositories.customer import CustomerRepository
from app.repositories.business import BusinessRepository
from app.services.storage import get_storage_service
from app.services.wallets import PassCoordinator, create_pass_coordinator
from app.core.permissions import (
    require_any_access,
    require_owner_access,
    BusinessAccessContext,
)
from app.core.entitlements import require_can_create_design

router = APIRouter()


def get_pass_coordinator() -> PassCoordinator:
    """Dependency to get PassCoordinator."""
    return create_pass_coordinator()


def _design_to_response(design: dict) -> CardDesignResponse:
    """Convert a design dict to a response with URLs."""
    return CardDesignResponse(
        id=design["id"],
        name=design["name"],
        is_active=design["is_active"],
        organization_name=design["organization_name"],
        description=design["description"],
        logo_text=design.get("logo_text"),
        foreground_color=design["foreground_color"],
        background_color=design["background_color"],
        label_color=design["label_color"],
        total_stamps=design["total_stamps"],
        stamp_filled_color=design["stamp_filled_color"],
        stamp_empty_color=design["stamp_empty_color"],
        stamp_border_color=design["stamp_border_color"],
        stamp_icon=design.get("stamp_icon", "checkmark"),
        reward_icon=design.get("reward_icon", "gift"),
        icon_color=design.get("icon_color", "#ffffff"),
        # URLs are stored in *_path columns (Supabase Storage URLs)
        logo_url=design.get("logo_path"),
        custom_filled_stamp_url=design.get("custom_filled_stamp_path"),
        custom_empty_stamp_url=design.get("custom_empty_stamp_path"),
        strip_background_url=design.get("strip_background_path"),
        secondary_fields=design.get("secondary_fields", []),
        auxiliary_fields=design.get("auxiliary_fields", []),
        back_fields=design.get("back_fields", []),
        created_at=design.get("created_at"),
        updated_at=design.get("updated_at"),
    )


@router.get("/{business_id}", response_model=list[CardDesignResponse])
def list_designs(ctx: BusinessAccessContext = Depends(require_any_access)):
    """Get all card designs for a business (requires membership)."""
    designs = CardDesignRepository.get_all(ctx.business_id)
    return [_design_to_response(d) for d in designs]


@router.get("/{business_id}/active", response_model=CardDesignResponse | None)
def get_active_design(business_id: str):
    """Get the currently active card design for a business (public for pass generation)."""
    business = BusinessRepository.get_by_id(business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    design = CardDesignRepository.get_active(business_id)
    if not design:
        return None
    return _design_to_response(design)


@router.get("/{business_id}/{design_id}", response_model=CardDesignResponse)
def get_design(
    design_id: str,
    ctx: BusinessAccessContext = Depends(require_any_access)
):
    """Get a specific card design (requires membership)."""
    design = CardDesignRepository.get_by_id(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    # Verify design belongs to the business
    if design.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Design not found")

    return _design_to_response(design)


@router.post("/{business_id}", response_model=CardDesignResponse)
def create_design(
    data: CardDesignCreate,
    ctx: BusinessAccessContext = Depends(require_owner_access),
    _entitlement: BusinessAccessContext = Depends(require_can_create_design),
    coordinator: PassCoordinator = Depends(get_pass_coordinator),
):
    """Create a new card design for a business (requires owner role and plan allowance).

    Pre-generates strip images for both Apple and Google Wallet (synchronous).
    """
    # Convert PassField objects to dicts for storage
    secondary_fields = [f.model_dump() for f in data.secondary_fields]
    auxiliary_fields = [f.model_dump() for f in data.auxiliary_fields]
    back_fields = [f.model_dump() for f in data.back_fields]

    design = CardDesignRepository.create(
        business_id=ctx.business_id,
        name=data.name,
        organization_name=data.organization_name,
        description=data.description,
        logo_text=data.logo_text,
        foreground_color=data.foreground_color,
        background_color=data.background_color,
        label_color=data.label_color,
        total_stamps=data.total_stamps,
        stamp_filled_color=data.stamp_filled_color,
        stamp_empty_color=data.stamp_empty_color,
        stamp_border_color=data.stamp_border_color,
        stamp_icon=data.stamp_icon,
        reward_icon=data.reward_icon,
        icon_color=data.icon_color,
        secondary_fields=secondary_fields,
        auxiliary_fields=auxiliary_fields,
        back_fields=back_fields,
    )

    if not design:
        raise HTTPException(status_code=500, detail="Failed to create design")

    # Pre-generate strip images for both Apple and Google Wallet (synchronous)
    try:
        coordinator.pregenerate_strips_for_design(design, ctx.business_id)
    except Exception as e:
        print(f"Strip pre-generation error: {e}")
        # Don't fail design creation if strip generation fails

    return _design_to_response(design)


@router.put("/{business_id}/{design_id}", response_model=CardDesignResponse)
async def update_design(
    design_id: str,
    data: CardDesignUpdate,
    background_tasks: BackgroundTasks,
    ctx: BusinessAccessContext = Depends(require_owner_access),
    coordinator: PassCoordinator = Depends(get_pass_coordinator),
):
    """Update a card design (requires owner role).

    If design is active and affects strips, regenerates strips in background
    and notifies customers after completion.
    """
    existing = CardDesignRepository.get_by_id(design_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Design not found")

    # Verify design belongs to the business
    if existing.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Design not found")

    # Build update dict from non-None fields
    update_data = {}
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            # Convert PassField lists to dicts
            if field in ["secondary_fields", "auxiliary_fields", "back_fields"]:
                update_data[field] = [f if isinstance(f, dict) else f.model_dump() for f in value]
            else:
                update_data[field] = value

    if update_data:
        design = CardDesignRepository.update(design_id, **update_data)
    else:
        design = existing

    # Check if changes affect strip appearance
    # Only regenerate if the VALUE actually changed, not just if the field was sent
    strip_affecting_fields = {
        "background_color", "stamp_filled_color", "stamp_empty_color",
        "stamp_border_color", "total_stamps", "stamp_icon", "reward_icon",
        "icon_color"
    }
    affects_strips = any(
        field in update_data and update_data[field] != existing.get(field)
        for field in strip_affecting_fields
    )

    if update_data and affects_strips:
        business = BusinessRepository.get_by_id(ctx.business_id)

        if existing.get("is_active"):
            # Active design: regenerate strips in background, then notify customers
            async def regenerate_and_notify():
                try:
                    await coordinator.on_design_updated(
                        business=business,
                        design=design,
                        regenerate_strips=True,
                    )
                except Exception as e:
                    print(f"Background design update error: {e}")

            background_tasks.add_task(regenerate_and_notify)
        else:
            # Inactive design: regenerate strips synchronously
            try:
                coordinator.pregenerate_strips_for_design(design, ctx.business_id)
            except Exception as e:
                print(f"Strip regeneration error: {e}")

    return _design_to_response(design)


@router.delete("/{business_id}/{design_id}")
def delete_design(
    design_id: str,
    ctx: BusinessAccessContext = Depends(require_owner_access),
    coordinator: PassCoordinator = Depends(get_pass_coordinator),
):
    """Delete a card design (requires owner role)."""
    existing = CardDesignRepository.get_by_id(design_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Design not found")

    # Verify design belongs to the business
    if existing.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Design not found")

    if existing["is_active"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the active design. Activate another design first."
        )

    # Delete uploaded assets from Supabase Storage
    storage = get_storage_service()
    storage.delete_card_assets(ctx.business_id, design_id)
    storage.delete_strip_images(ctx.business_id, design_id)

    # Delete strip image records from database
    coordinator.strips.delete_strips_for_design(design_id)

    CardDesignRepository.delete(design_id)
    return {"message": "Design deleted"}


@router.post("/{business_id}/{design_id}/activate", response_model=CardDesignResponse)
async def activate_design(
    design_id: str,
    background_tasks: BackgroundTasks,
    ctx: BusinessAccessContext = Depends(require_owner_access),
    coordinator: PassCoordinator = Depends(get_pass_coordinator),
):
    """Set a design as active and push updates to all passes (requires owner role).

    Strips should already exist from design creation. Updates Google Wallet class
    and sends push notifications to all customers.
    """
    design = CardDesignRepository.get_by_id(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    # Verify design belongs to the business
    if design.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Design not found")

    # Get business for wallet updates
    business = BusinessRepository.get_by_id(ctx.business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Activate the design (deactivates others for this business)
    design = CardDesignRepository.set_active(ctx.business_id, design_id)

    # Handle activation: update Google class and notify customers
    result = coordinator.on_design_activated(business, design)

    # Send notifications to all customers in background
    async def notify_all_customers():
        try:
            await coordinator.on_design_updated(
                business=business,
                design=design,
                regenerate_strips=not result.get("strips_exist", False),
            )
        except Exception as e:
            print(f"Customer notification error: {e}")

    background_tasks.add_task(notify_all_customers)

    return _design_to_response(design)


@router.post("/{business_id}/{design_id}/upload/logo", response_model=UploadResponse)
async def upload_logo(
    design_id: str,
    file: UploadFile = File(...),
    ctx: BusinessAccessContext = Depends(require_owner_access)
):
    """Upload a logo image for a design (requires owner role)."""
    design = CardDesignRepository.get_by_id(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    # Verify design belongs to the business
    if design.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Design not found")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Upload to Supabase Storage
    storage = get_storage_service()
    content = await file.read()
    url = storage.upload_card_logo(ctx.business_id, design_id, content)

    # Update design with logo URL (stored in logo_path column)
    CardDesignRepository.update(design_id, logo_path=url)

    return UploadResponse(
        id=design_id,
        asset_type="logo",
        url=url,
        filename="logo.png",
    )


@router.post("/{business_id}/{design_id}/upload/stamp/{stamp_type}", response_model=UploadResponse)
async def upload_stamp(
    design_id: str,
    stamp_type: str,
    file: UploadFile = File(...),
    ctx: BusinessAccessContext = Depends(require_owner_access)
):
    """Upload a custom stamp icon (requires owner role)."""
    if stamp_type not in ["filled", "empty"]:
        raise HTTPException(status_code=400, detail="stamp_type must be 'filled' or 'empty'")

    design = CardDesignRepository.get_by_id(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    # Verify design belongs to the business
    if design.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Design not found")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Upload to Supabase Storage
    storage = get_storage_service()
    content = await file.read()
    url = storage.upload_card_stamp(ctx.business_id, design_id, stamp_type, content)

    # Update design with stamp URL (stored in *_path columns)
    if stamp_type == "filled":
        CardDesignRepository.update(design_id, custom_filled_stamp_path=url)
    else:
        CardDesignRepository.update(design_id, custom_empty_stamp_path=url)

    return UploadResponse(
        id=design_id,
        asset_type=f"stamp_{stamp_type}",
        url=url,
        filename=f"stamp_{stamp_type}.png",
    )


@router.post("/{business_id}/{design_id}/upload/strip-background", response_model=UploadResponse)
async def upload_strip_background(
    design_id: str,
    file: UploadFile = File(...),
    ctx: BusinessAccessContext = Depends(require_owner_access)
):
    """Upload a custom strip background image (requires owner role)."""
    design = CardDesignRepository.get_by_id(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    # Verify design belongs to the business
    if design.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Design not found")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Upload to Supabase Storage
    storage = get_storage_service()
    content = await file.read()
    url = storage.upload_card_strip_background(ctx.business_id, design_id, content)

    # Update design with strip background URL (stored in strip_background_path column)
    CardDesignRepository.update(design_id, strip_background_path=url)

    return UploadResponse(
        id=design_id,
        asset_type="strip_background",
        url=url,
        filename="strip_background.png",
    )
