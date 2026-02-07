import secrets

from fastapi import APIRouter, HTTPException, Depends

from app.domain.schemas import CustomerCreate, CustomerResponse
from app.repositories.customer import CustomerRepository
from app.repositories.card_design import CardDesignRepository
from app.repositories.business import BusinessRepository
from app.services.wallets import PassCoordinator, create_pass_coordinator
from app.core.config import get_public_base_url
from app.core.permissions import require_any_access, BusinessAccessContext

router = APIRouter()


def get_pass_coordinator() -> PassCoordinator:
    """Dependency to get PassCoordinator."""
    return create_pass_coordinator()


@router.post("/{business_id}", response_model=CustomerResponse)
def create_new_customer(
    customer: CustomerCreate,
    ctx: BusinessAccessContext = Depends(require_any_access),
    coordinator: PassCoordinator = Depends(get_pass_coordinator),
):
    """Create a new customer for a business (requires membership).

    Returns URLs for both Apple Wallet and Google Wallet.
    """
    base_url = get_public_base_url()

    # Get business and design for wallet URL generation
    business = BusinessRepository.get_by_id(ctx.business_id)
    design = CardDesignRepository.get_active(ctx.business_id)

    existing = CustomerRepository.get_by_email(ctx.business_id, customer.email)
    if existing:
        # Generate wallet URLs for existing customer
        wallet_urls = {"apple_url": f"{base_url}/passes/{existing['id']}", "google_url": None}
        if business and design:
            try:
                wallet_urls = coordinator.get_wallet_urls(existing, business, design)
            except Exception as e:
                print(f"Wallet URL generation error: {e}")

        return CustomerResponse(
            id=existing["id"],
            name=existing["name"],
            email=existing["email"],
            stamps=existing["stamps"],
            pass_url=wallet_urls.get("apple_url"),
            google_wallet_url=wallet_urls.get("google_url"),
        )

    auth_token = secrets.token_hex(16)

    result = CustomerRepository.create(ctx.business_id, customer.name, customer.email, auth_token)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create customer")

    # Generate wallet URLs for new customer
    wallet_urls = {"apple_url": f"{base_url}/passes/{result['id']}", "google_url": None}
    if business and design:
        try:
            wallet_urls = coordinator.on_customer_created(result, business, design)
        except Exception as e:
            print(f"Wallet URL generation error: {e}")

    return CustomerResponse(
        id=result["id"],
        name=result["name"],
        email=result["email"],
        stamps=result["stamps"],
        pass_url=wallet_urls.get("apple_url"),
        google_wallet_url=wallet_urls.get("google_url"),
    )


@router.get("/{business_id}", response_model=list[CustomerResponse])
def list_customers(
    ctx: BusinessAccessContext = Depends(require_any_access),
    coordinator: PassCoordinator = Depends(get_pass_coordinator),
):
    """Get all customers for a business (requires membership).

    Returns URLs for both Apple Wallet and Google Wallet for each customer.
    """
    base_url = get_public_base_url()
    customers = CustomerRepository.get_all(ctx.business_id)

    # Get business and design for wallet URL generation
    business = BusinessRepository.get_by_id(ctx.business_id)
    design = CardDesignRepository.get_active(ctx.business_id)

    results = []
    for c in customers:
        wallet_urls = {"apple_url": f"{base_url}/passes/{c['id']}", "google_url": None}
        if business and design:
            try:
                wallet_urls = coordinator.get_wallet_urls(c, business, design)
            except Exception:
                pass  # Use default URLs

        results.append(CustomerResponse(
            id=c["id"],
            name=c["name"],
            email=c["email"],
            stamps=c["stamps"],
            pass_url=wallet_urls.get("apple_url"),
            google_wallet_url=wallet_urls.get("google_url"),
        ))

    return results


@router.get("/{business_id}/{customer_id}", response_model=CustomerResponse)
def get_customer_info(
    customer_id: str,
    ctx: BusinessAccessContext = Depends(require_any_access),
    coordinator: PassCoordinator = Depends(get_pass_coordinator),
):
    """Get customer details (requires membership).

    Returns URLs for both Apple Wallet and Google Wallet.
    """
    base_url = get_public_base_url()
    customer = CustomerRepository.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Verify customer belongs to the business
    if customer.get("business_id") != ctx.business_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Get business and design for wallet URL generation
    business = BusinessRepository.get_by_id(ctx.business_id)
    design = CardDesignRepository.get_active(ctx.business_id)

    wallet_urls = {"apple_url": f"{base_url}/passes/{customer['id']}", "google_url": None}
    if business and design:
        try:
            wallet_urls = coordinator.get_wallet_urls(customer, business, design)
        except Exception as e:
            print(f"Wallet URL generation error: {e}")

    return CustomerResponse(
        id=customer["id"],
        name=customer["name"],
        email=customer["email"],
        stamps=customer["stamps"],
        pass_url=wallet_urls.get("apple_url"),
        google_wallet_url=wallet_urls.get("google_url"),
    )
