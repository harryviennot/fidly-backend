import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends

from app.domain.schemas import (
    CardDesignCreate,
    CardDesignUpdate,
    CardDesignResponse,
    UploadResponse,
)
from app.repositories.card_design import CardDesignRepository
from app.repositories.customer import CustomerRepository
from app.repositories.device import DeviceRepository
from app.repositories.business import BusinessRepository
from app.services.apns import APNsClient
from app.api.deps import get_apns_client
from app.core.config import settings

router = APIRouter()

# Upload directory for design assets
UPLOADS_DIR = Path(__file__).parent.parent.parent.parent / "uploads" / "designs"


def _design_to_response(design: dict) -> CardDesignResponse:
    """Convert a design dict to a response with URLs."""
    logo_url = None
    if design.get("logo_path"):
        logo_url = f"{settings.base_url}/designs/uploads/{design['id']}/{design['logo_path']}"

    filled_stamp_url = None
    if design.get("custom_filled_stamp_path"):
        filled_stamp_url = f"{settings.base_url}/designs/uploads/{design['id']}/{design['custom_filled_stamp_path']}"

    empty_stamp_url = None
    if design.get("custom_empty_stamp_path"):
        empty_stamp_url = f"{settings.base_url}/designs/uploads/{design['id']}/{design['custom_empty_stamp_path']}"

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
        logo_url=logo_url,
        custom_filled_stamp_url=filled_stamp_url,
        custom_empty_stamp_url=empty_stamp_url,
        secondary_fields=design.get("secondary_fields", []),
        auxiliary_fields=design.get("auxiliary_fields", []),
        back_fields=design.get("back_fields", []),
        created_at=design.get("created_at"),
        updated_at=design.get("updated_at"),
    )


@router.get("/{business_id}", response_model=list[CardDesignResponse])
def list_designs(business_id: str):
    """Get all card designs for a business."""
    business = BusinessRepository.get_by_id(business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    designs = CardDesignRepository.get_all(business_id)
    return [_design_to_response(d) for d in designs]


@router.get("/{business_id}/active", response_model=CardDesignResponse | None)
def get_active_design(business_id: str):
    """Get the currently active card design for a business."""
    business = BusinessRepository.get_by_id(business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    design = CardDesignRepository.get_active(business_id)
    if not design:
        return None
    return _design_to_response(design)


@router.get("/{business_id}/{design_id}", response_model=CardDesignResponse)
def get_design(business_id: str, design_id: str):
    """Get a specific card design."""
    design = CardDesignRepository.get_by_id(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    # Verify design belongs to the business
    if design.get("business_id") != business_id:
        raise HTTPException(status_code=404, detail="Design not found")

    return _design_to_response(design)


@router.post("/{business_id}", response_model=CardDesignResponse)
def create_design(business_id: str, data: CardDesignCreate):
    """Create a new card design for a business."""
    business = BusinessRepository.get_by_id(business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Convert PassField objects to dicts for storage
    secondary_fields = [f.model_dump() for f in data.secondary_fields]
    auxiliary_fields = [f.model_dump() for f in data.auxiliary_fields]
    back_fields = [f.model_dump() for f in data.back_fields]

    design = CardDesignRepository.create(
        business_id=business_id,
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
        secondary_fields=secondary_fields,
        auxiliary_fields=auxiliary_fields,
        back_fields=back_fields,
    )

    if not design:
        raise HTTPException(status_code=500, detail="Failed to create design")

    return _design_to_response(design)


@router.put("/{business_id}/{design_id}", response_model=CardDesignResponse)
def update_design(business_id: str, design_id: str, data: CardDesignUpdate):
    """Update a card design."""
    existing = CardDesignRepository.get_by_id(design_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Design not found")

    # Verify design belongs to the business
    if existing.get("business_id") != business_id:
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

    return _design_to_response(design)


@router.delete("/{business_id}/{design_id}")
def delete_design(business_id: str, design_id: str):
    """Delete a card design."""
    existing = CardDesignRepository.get_by_id(design_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Design not found")

    # Verify design belongs to the business
    if existing.get("business_id") != business_id:
        raise HTTPException(status_code=404, detail="Design not found")

    if existing["is_active"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the active design. Activate another design first."
        )

    # Delete uploaded assets
    design_uploads = UPLOADS_DIR / design_id
    if design_uploads.exists():
        shutil.rmtree(design_uploads)

    CardDesignRepository.delete(design_id)
    return {"message": "Design deleted"}


@router.post("/{business_id}/{design_id}/activate", response_model=CardDesignResponse)
async def activate_design(
    business_id: str,
    design_id: str,
    apns_client: APNsClient = Depends(get_apns_client)
):
    """Set a design as active and push updates to all customer passes for this business."""
    design = CardDesignRepository.get_by_id(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    # Verify design belongs to the business
    if design.get("business_id") != business_id:
        raise HTTPException(status_code=404, detail="Design not found")

    # Activate the design (deactivates others for this business)
    design = CardDesignRepository.set_active(business_id, design_id)

    # Send push notifications to all registered devices for this business's customers
    customers = CustomerRepository.get_all(business_id)
    for customer in customers:
        push_tokens = DeviceRepository.get_push_tokens(customer["id"])
        if push_tokens:
            await apns_client.send_to_all_devices(push_tokens)

    return _design_to_response(design)


@router.post("/{business_id}/{design_id}/upload/logo", response_model=UploadResponse)
async def upload_logo(business_id: str, design_id: str, file: UploadFile = File(...)):
    """Upload a logo image for a design."""
    design = CardDesignRepository.get_by_id(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    # Verify design belongs to the business
    if design.get("business_id") != business_id:
        raise HTTPException(status_code=404, detail="Design not found")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Create upload directory
    design_uploads = UPLOADS_DIR / design_id
    design_uploads.mkdir(parents=True, exist_ok=True)

    # Save the file
    filename = "logo.png"
    filepath = design_uploads / filename
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    # Update design with logo path
    CardDesignRepository.update(design_id, logo_path=filename)

    return UploadResponse(
        id=design_id,
        asset_type="logo",
        url=f"{settings.base_url}/designs/uploads/{design_id}/{filename}",
        filename=filename,
    )


@router.post("/{business_id}/{design_id}/upload/stamp/{stamp_type}", response_model=UploadResponse)
async def upload_stamp(business_id: str, design_id: str, stamp_type: str, file: UploadFile = File(...)):
    """Upload a custom stamp icon (filled or empty)."""
    if stamp_type not in ["filled", "empty"]:
        raise HTTPException(status_code=400, detail="stamp_type must be 'filled' or 'empty'")

    design = CardDesignRepository.get_by_id(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    # Verify design belongs to the business
    if design.get("business_id") != business_id:
        raise HTTPException(status_code=404, detail="Design not found")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Create upload directory
    design_uploads = UPLOADS_DIR / design_id
    design_uploads.mkdir(parents=True, exist_ok=True)

    # Save the file
    filename = f"stamp_{stamp_type}.png"
    filepath = design_uploads / filename
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    # Update design with stamp path
    if stamp_type == "filled":
        CardDesignRepository.update(design_id, custom_filled_stamp_path=filename)
    else:
        CardDesignRepository.update(design_id, custom_empty_stamp_path=filename)

    return UploadResponse(
        id=design_id,
        asset_type=f"stamp_{stamp_type}",
        url=f"{settings.base_url}/designs/uploads/{design_id}/{filename}",
        filename=filename,
    )


@router.get("/uploads/{design_id}/{filename}")
def serve_upload(design_id: str, filename: str):
    """Serve an uploaded file."""
    from fastapi.responses import FileResponse

    filepath = UPLOADS_DIR / design_id / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(filepath)
