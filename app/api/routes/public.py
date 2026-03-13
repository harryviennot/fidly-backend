"""Public routes for customer-facing endpoints (no authentication required)."""

import secrets
import logging
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request

from app.domain.schemas import ContactFormRequest, CustomerPublicCreate, CustomerPublicResponse
from app.repositories.business import BusinessRepository
from app.repositories.customer import CustomerRepository
from app.repositories.card_design import CardDesignRepository
from app.services.email import get_email_service
from app.services.wallets import create_pass_coordinator
from app.core.config import settings
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

# Simple in-memory rate limiting for contact form
_contact_rate_limit: dict[str, list[float]] = defaultdict(list)
CONTACT_RATE_LIMIT_MAX = 3
CONTACT_RATE_LIMIT_WINDOW = 600  # 10 minutes


@router.post("/contact")
def send_contact(request: Request, data: ContactFormRequest):
    """Public contact form endpoint. Rate-limited to 3 per IP per 10 minutes."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Clean old entries and check rate limit
    _contact_rate_limit[client_ip] = [
        t for t in _contact_rate_limit[client_ip] if now - t < CONTACT_RATE_LIMIT_WINDOW
    ]
    if len(_contact_rate_limit[client_ip]) >= CONTACT_RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    _contact_rate_limit[client_ip].append(now)

    try:
        email_service = get_email_service()
        email_service.send_contact_email(
            name=data.name,
            email=data.email,
            subject=data.subject,
            message=data.message,
        )
    except Exception as e:
        logger.error(f"Contact form error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")

    return {"status": "sent"}


@router.post("/customers/{business_id}", response_model=CustomerPublicResponse)
@limiter.limit("10/minute")
def register_customer(request: Request, business_id: str, data: CustomerPublicCreate):
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
        "collect_name": "required",
        "collect_email": "required",
        "collect_phone": "off",
    })

    # Normalize legacy boolean values: True -> "required", False -> "off"
    def _normalize(val):
        if val is True:
            return "required"
        if val is False:
            return "off"
        return val or "off"

    name_mode = _normalize(data_collection.get("collect_name"))
    email_mode = _normalize(data_collection.get("collect_email"))
    phone_mode = _normalize(data_collection.get("collect_phone"))

    # Validate required fields based on business settings
    if name_mode == "required" and not data.name:
        raise HTTPException(status_code=400, detail="Name is required")

    if email_mode == "required" and not data.email:
        raise HTTPException(status_code=400, detail="Email is required")

    if phone_mode == "required" and not data.phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    # Only require at least one identifier if business requires email or phone
    if (email_mode == "required" or phone_mode == "required") and not data.email and not data.phone:
        raise HTTPException(
            status_code=400,
            detail="At least an email or phone number is required"
        )

    # Check if customer already exists (by email for this business)
    if data.email:
        existing = CustomerRepository.get_by_email(business_id, data.email)
        if existing:
            # Customer exists - generate wallet URLs and send via email
            pass_url = f"{settings.base_url}/passes/{existing['id']}"
            google_wallet_url = None

            # Generate both wallet URLs using PassCoordinator
            design = CardDesignRepository.get_active(business_id)
            if design:
                try:
                    coordinator = create_pass_coordinator()
                    wallet_urls = coordinator.get_wallet_urls(existing, business, design)
                    pass_url = wallet_urls.get("apple_url") or pass_url
                    google_wallet_url = wallet_urls.get("google_url")
                except Exception as e:
                    logger.error(f"Wallet URL generation error for existing customer: {e}")

            try:
                email_service = get_email_service()
                email_service.send_pass_email(
                    to=data.email,
                    customer_name=existing.get("name"),
                    business_name=business["name"],
                    pass_url=pass_url,
                    google_wallet_url=google_wallet_url,
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
