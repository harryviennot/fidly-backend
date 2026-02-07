"""Public routes for customer-facing endpoints (no authentication required)."""

import secrets
import logging

from fastapi import APIRouter, HTTPException

from app.domain.schemas import CustomerPublicCreate, CustomerPublicResponse
from app.repositories.business import BusinessRepository
from app.repositories.customer import CustomerRepository
from app.repositories.card_design import CardDesignRepository
from app.services.email import get_email_service
from app.services.wallets import create_pass_coordinator
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/customers/{business_id}", response_model=CustomerPublicResponse)
def register_customer(business_id: str, data: CustomerPublicCreate):
    """
    Public customer registration endpoint.

    Creates a new customer for the specified business or sends the existing
    customer's pass via email if they already have a card.

    No authentication required - this is the public-facing customer signup.
    """
    # Verify business exists
    business = BusinessRepository.get_by_id(business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Get customer data collection settings
    business_settings = business.get("settings", {})
    data_collection = business_settings.get("customer_data_collection", {
        "collect_name": True,
        "collect_email": True,
        "collect_phone": False,
    })

    # Validate required fields based on business settings
    if data_collection.get("collect_name") and not data.name:
        raise HTTPException(status_code=400, detail="Name is required")

    if data_collection.get("collect_email") and not data.email:
        raise HTTPException(status_code=400, detail="Email is required")

    if data_collection.get("collect_phone") and not data.phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    # Check if at least one identifier is provided (email or phone)
    if not data.email and not data.phone:
        raise HTTPException(
            status_code=400,
            detail="At least an email or phone number is required"
        )

    # Check if customer already exists (by email for this business)
    if data.email:
        existing = CustomerRepository.get_by_email(business_id, data.email)
        if existing:
            # Customer exists - send pass via email for security
            pass_url = f"{settings.base_url}/passes/{existing['id']}"

            try:
                email_service = get_email_service()
                email_service.send_pass_email(
                    to=data.email,
                    customer_name=existing.get("name"),
                    business_name=business["name"],
                    pass_url=pass_url,
                )
                logger.info(f"Sent existing pass email to {data.email} for business {business_id}")
            except Exception as e:
                logger.error(f"Failed to send pass email: {e}")
                # Don't fail the request if email fails - customer still exists

            return CustomerPublicResponse(
                status="exists_email_sent",
                message="A card already exists for this email. We've sent it to your inbox.",
            )

    # Create new customer
    auth_token = secrets.token_hex(16)
    customer_name = data.name or "Customer"  # Fallback if name not collected
    customer_email = data.email or f"anonymous-{secrets.token_hex(8)}@placeholder.local"

    result = CustomerRepository.create(
        business_id=business_id,
        name=customer_name,
        email=customer_email,
        auth_token=auth_token,
    )

    if not result:
        raise HTTPException(status_code=500, detail="Failed to create customer")

    # Generate wallet URLs using PassCoordinator
    pass_url = f"{settings.base_url}/passes/{result['id']}"
    google_wallet_url = None

    design = CardDesignRepository.get_active(business_id)
    if business and design:
        try:
            coordinator = create_pass_coordinator()
            wallet_urls = coordinator.on_customer_created(result, business, design)
            pass_url = wallet_urls.get("apple_url") or pass_url
            google_wallet_url = wallet_urls.get("google_url")
        except Exception as e:
            logger.error(f"Wallet URL generation error: {e}")

    logger.info(f"Created new customer {result['id']} for business {business_id}")

    return CustomerPublicResponse(
        status="created",
        customer_id=result["id"],
        pass_url=pass_url,
        google_wallet_url=google_wallet_url,
        message="Your loyalty card is ready! Add it to your wallet.",
    )
