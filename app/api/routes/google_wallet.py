"""
Google Wallet API routes.
Handles pass creation, callbacks, and JWT generation.
"""

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from typing import Optional

from app.repositories.customer import CustomerRepository
from app.repositories.card_design import CardDesignRepository
from app.repositories.device import DeviceRepository
from app.repositories.google_wallet import GoogleWalletRepository
from app.services.google_wallet import (
    create_google_wallet_client,
    is_google_wallet_configured,
)
from app.services.google_pass_generator import create_google_pass_generator

router = APIRouter()


class SaveUrlResponse(BaseModel):
    """Response containing the Google Wallet save URL."""
    save_url: str
    object_id: str
    configured: bool = True


class CallbackResponse(BaseModel):
    """Response for callback processing."""
    status: str
    message: Optional[str] = None


class ClassSyncResponse(BaseModel):
    """Response for class sync operation."""
    status: str
    class_id: str
    action: str  # "created" or "updated"


@router.get("/status")
def get_google_wallet_status():
    """
    Check if Google Wallet is configured and available.

    Returns configuration status and issuer ID (if configured).
    """
    from app.core.config import settings

    configured = is_google_wallet_configured()

    return {
        "configured": configured,
        "issuer_id": settings.google_wallet_issuer_id if configured else None,
    }


@router.get("/save-url/{customer_id}", response_model=SaveUrlResponse)
def get_google_wallet_save_url(customer_id: str):
    """
    Generate a Google Wallet "Add to Wallet" URL for a customer.

    This creates a signed JWT that allows the customer to add the pass
    to their Google Wallet. The pass is created on-the-fly when saved.
    """
    # Check if Google Wallet is configured
    if not is_google_wallet_configured():
        raise HTTPException(
            status_code=503,
            detail="Google Wallet is not configured"
        )

    customer = CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    business_id = customer.get("business_id")
    if not business_id:
        raise HTTPException(status_code=400, detail="Customer has no business association")

    design = CardDesignRepository.get_active(business_id)
    if not design:
        raise HTTPException(status_code=404, detail="No active design for business")

    try:
        google_client = create_google_wallet_client()
        pass_generator = create_google_pass_generator()

        # Generate class and object data
        class_id = pass_generator.generate_class_id(business_id)
        object_id = pass_generator.generate_object_id(customer_id)

        # Get callback URL for save/delete events
        from app.core.config import settings
        callback_url = f"{settings.base_url}/google-wallet/callback"

        class_data = pass_generator.design_to_class(design, business_id, callback_url)
        object_data = pass_generator.customer_to_object(customer, class_id, design)

        # Check if class already exists in Google
        existing_class = google_client.get_loyalty_class(class_id)

        # Create JWT with embedded class (if new) and object
        jwt_token = google_client.create_save_jwt(
            object_data=object_data,
            class_data=class_data if not existing_class else None
        )

        save_url = google_client.get_save_url(jwt_token)

        return SaveUrlResponse(
            save_url=save_url,
            object_id=object_id,
            configured=True
        )

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Google Wallet credentials not found: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate Google Wallet URL: {e}"
        )


@router.get("/hero/{business_id}")
def get_hero_image(business_id: str, stamps: int = 0, v: Optional[str] = None):
    """
    Generate a hero image (stamp strip) for Google Wallet.

    This endpoint is called by Google to fetch the hero image.
    Returns a PNG image optimized for Google Wallet (1032x336 pixels).

    Args:
        business_id: The business UUID
        stamps: Current stamp count to display (default 0 for class template)
        v: Version parameter for cache busting
    """
    design = CardDesignRepository.get_active(business_id)
    if not design:
        raise HTTPException(status_code=404, detail="No active design")

    try:
        pass_generator = create_google_pass_generator()
        image_bytes = pass_generator.generate_hero_image(design, stamps)

        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                "Content-Type": "image/png",
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate hero image: {e}"
        )


@router.post("/callback", response_model=CallbackResponse)
async def google_wallet_callback(request: Request):
    """
    Receive callbacks from Google Wallet.

    Google sends POST requests when:
    - A pass is saved to a wallet (eventType: "save")
    - A pass is deleted from a wallet (eventType: "del")

    Payload includes:
    - classId: Fully qualified class ID
    - objectId: Fully qualified object ID
    - eventType: "save" or "del"
    - nonce: Unique identifier for deduplication
    - expTimeMillis: Expiration timestamp
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = body.get("eventType")
    object_id = body.get("objectId")
    class_id = body.get("classId")
    nonce = body.get("nonce")

    if not object_id:
        return CallbackResponse(status="ignored", message="No objectId provided")

    # Extract customer_id from object_id (format: issuer_id.customer_uuid_without_hyphens)
    parts = object_id.split(".")
    if len(parts) != 2:
        return CallbackResponse(status="ignored", message="Invalid objectId format")

    # The customer ID in object_id has hyphens removed, need to reconstruct
    # For now, store the object_id as-is since we'll look up by object_id anyway
    customer_id_clean = parts[1]

    # Try to find the customer by looking up existing registrations or matching UUID pattern
    # Since we store object_id, we can use it directly for lookups
    from app.core.config import settings

    if event_type == "save":
        # Customer added pass to wallet
        # We need to find the customer_id from the object_id
        # The object_id format is: issuer_id.customer_uuid_without_hyphens
        # We need to convert back to UUID format

        # Try to reconstruct UUID (8-4-4-4-12 format)
        if len(customer_id_clean) == 32:
            customer_id = f"{customer_id_clean[:8]}-{customer_id_clean[8:12]}-{customer_id_clean[12:16]}-{customer_id_clean[16:20]}-{customer_id_clean[20:]}"
        else:
            customer_id = customer_id_clean

        # Verify customer exists
        customer = CustomerRepository.get_by_id(customer_id)
        if customer:
            DeviceRepository.register_google(customer_id, object_id)
            print(f"Google Wallet pass saved: {object_id} for customer {customer_id}")
            return CallbackResponse(status="ok", message="Pass registered")
        else:
            print(f"Google Wallet callback: customer not found for {customer_id}")
            return CallbackResponse(status="ignored", message="Customer not found")

    elif event_type == "del":
        # Customer removed pass from wallet
        # Find registration by object_id
        from database.connection import get_db
        db = get_db()
        result = db.table("push_registrations").select("customer_id").eq(
            "google_object_id", object_id
        ).limit(1).execute()

        if result.data:
            customer_id = result.data[0]["customer_id"]
            DeviceRepository.unregister_google(customer_id, object_id)
            print(f"Google Wallet pass deleted: {object_id}")
            return CallbackResponse(status="ok", message="Pass unregistered")
        else:
            return CallbackResponse(status="ignored", message="Registration not found")

    return CallbackResponse(status="ignored", message=f"Unknown event type: {event_type}")


@router.post("/sync-class/{business_id}", response_model=ClassSyncResponse)
async def sync_loyalty_class(business_id: str):
    """
    Create or update the LoyaltyClass for a business.

    Called when:
    - Business activates their first design
    - Design is updated (propagates to all customers)

    This is typically called automatically when a design is activated,
    but can also be called manually to force a sync.
    """
    if not is_google_wallet_configured():
        raise HTTPException(
            status_code=503,
            detail="Google Wallet is not configured"
        )

    design = CardDesignRepository.get_active(business_id)
    if not design:
        raise HTTPException(status_code=404, detail="No active design for business")

    try:
        google_client = create_google_wallet_client()
        pass_generator = create_google_pass_generator()

        # Get callback URL
        from app.core.config import settings
        callback_url = f"{settings.base_url}/google-wallet/callback"

        class_id = pass_generator.generate_class_id(business_id)
        class_data = pass_generator.design_to_class(design, business_id, callback_url)

        existing = google_client.get_loyalty_class(class_id)

        if existing:
            # Update existing class
            google_client.update_loyalty_class(class_id, class_data)
            action = "updated"
        else:
            # Create new class
            google_client.create_loyalty_class(class_id, class_data)
            action = "created"

        # Store/update in our database
        GoogleWalletRepository.upsert_class(
            business_id=business_id,
            card_design_id=design.get("id"),
            class_id=class_id,
            class_data=class_data
        )

        return ClassSyncResponse(
            status="ok",
            class_id=class_id,
            action=action
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync class: {e}"
        )


@router.post("/update-object/{customer_id}")
async def update_loyalty_object(
    customer_id: str,
    notify: bool = False
):
    """
    Manually update a customer's Google Wallet pass.

    This is typically called automatically when stamps are added,
    but can be called manually to force an update.

    Args:
        customer_id: The customer UUID
        notify: Whether to send a push notification (limited to 3/24h)
    """
    if not is_google_wallet_configured():
        raise HTTPException(
            status_code=503,
            detail="Google Wallet is not configured"
        )

    customer = CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get Google Wallet registrations for this customer
    google_object_ids = DeviceRepository.get_google_registrations(customer_id)
    if not google_object_ids:
        raise HTTPException(
            status_code=404,
            detail="Customer has no Google Wallet registration"
        )

    try:
        google_client = create_google_wallet_client()

        results = []
        for object_id in google_object_ids:
            google_client.update_loyalty_object(
                object_id,
                {"stamps": customer.get("stamps", 0)},
                notify=notify
            )
            results.append({"object_id": object_id, "status": "updated"})

        return {"status": "ok", "updated": results}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update object: {e}"
        )
