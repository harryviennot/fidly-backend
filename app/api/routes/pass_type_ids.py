"""Admin API for managing the per-business Apple Pass Type ID certificate pool."""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from postgrest.exceptions import APIError

from app.core.permissions import require_owner_access, BusinessAccessContext
from app.core.security import require_superadmin
from app.repositories.pass_type_id import PassTypeIdRepository
from app.services.certificate_manager import get_certificate_manager

router = APIRouter()


@router.post("/upload")
def upload_pass_type_id(
    identifier: str = Form(...),
    team_id: str = Form(...),
    p12_file: UploadFile = File(...),
    p12_password: str | None = Form(None),
    _: dict = Depends(require_superadmin),
):
    """Upload a .p12 certificate to add to the pool.

    Extracts signer cert, key, and APNs combined from .p12,
    encrypts them, and stores in the database.

    Requires service-level auth (not business-scoped).
    """
    cert_manager = get_certificate_manager()

    # Read and extract from .p12
    p12_data = p12_file.file.read()
    try:
        signer_cert, signer_key, apns_combined = cert_manager.extract_from_p12(
            p12_data, p12_password
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract .p12: {e}")

    # Encrypt
    signer_cert_encrypted = cert_manager.encrypt(signer_cert)
    signer_key_encrypted = cert_manager.encrypt(signer_key)
    apns_combined_encrypted = cert_manager.encrypt(apns_combined)

    # Store in pool
    try:
        record = PassTypeIdRepository.create(
            identifier=identifier,
            team_id=team_id,
            signer_cert_encrypted=signer_cert_encrypted,
            signer_key_encrypted=signer_key_encrypted,
            apns_combined_encrypted=apns_combined_encrypted,
        )
    except APIError as e:
        if "23505" in str(e):
            raise HTTPException(status_code=409, detail=f"Identifier '{identifier}' already exists in the pool")
        raise

    if not record:
        raise HTTPException(status_code=500, detail="Failed to store pass type ID")

    return {
        "id": record["id"],
        "identifier": record["identifier"],
        "status": record["status"],
    }


@router.get("/pool")
def get_pool_stats(_: dict = Depends(require_superadmin)):
    """Get pool statistics (available/assigned/revoked counts)."""
    return PassTypeIdRepository.get_pool_stats()


@router.get("/")
def list_pass_type_ids(_: dict = Depends(require_superadmin)):
    """List all pass type IDs with assignment info."""
    return PassTypeIdRepository.list_all()


@router.post("/{pass_type_id_id}/revoke")
def revoke_pass_type_id(pass_type_id_id: str, _: dict = Depends(require_superadmin)):
    """Mark a pass type ID as revoked."""
    existing = PassTypeIdRepository.get_by_id(pass_type_id_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Pass type ID not found")

    record = PassTypeIdRepository.revoke(pass_type_id_id)
    if not record:
        raise HTTPException(status_code=500, detail="Failed to revoke")

    return {
        "id": record["id"],
        "identifier": record["identifier"],
        "status": record["status"],
    }
