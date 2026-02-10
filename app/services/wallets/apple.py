"""
Apple Wallet Service wrapper.

Provides a unified interface for Apple Wallet operations,
wrapping the existing PassGenerator and APNsClient.
"""

import asyncio
from pathlib import Path
from typing import Optional

from app.core.config import settings, get_public_base_url
from app.services.apns import APNsClient, create_apns_client, create_apns_client_for_business, create_demo_apns_client
from app.services.pass_generator import PassGenerator, create_pass_generator_for_business
from app.services.certificate_manager import get_certificate_manager
from app.repositories.wallet_registration import WalletRegistrationRepository
from app.repositories.card_design import CardDesignRepository


class AppleWalletService:
    """
    Service for creating and managing Apple Wallet passes.

    Wraps PassGenerator for pass creation and APNsClient for push updates.
    """

    def __init__(
        self,
        pass_generator: Optional[PassGenerator] = None,
        apns_client: Optional[APNsClient] = None,
    ):
        self._pass_generator = pass_generator
        self._apns_client = apns_client

    def _get_pass_generator(
        self,
        business_id: str | None = None,
        design: dict | None = None,
        primary_locale: str = "fr",
        translations: dict | None = None,
    ) -> PassGenerator:
        """Get or create a PassGenerator instance.

        If business_id is provided, loads per-business certs via CertificateManager.
        """
        if self._pass_generator:
            return self._pass_generator

        if business_id:
            return create_pass_generator_for_business(
                business_id,
                design=design,
                primary_locale=primary_locale,
                translations=translations,
            )

        # Fallback to shared certs (legacy/demo)
        return PassGenerator(
            team_id=settings.apple_team_id,
            pass_type_id=settings.apple_pass_type_id,
            base_url=get_public_base_url(),
            signer_cert_pem=Path(settings.cert_path).read_bytes(),
            signer_key_pem=Path(settings.key_path).read_bytes(),
            wwdr_cert_pem=Path(settings.wwdr_path).read_bytes(),
            design=design,
            primary_locale=primary_locale,
            translations=translations,
        )

    def _get_apns_client(self, business_id: str | None = None) -> APNsClient:
        """Get or create an APNsClient instance.

        If business_id is provided, loads per-business certs.
        """
        if self._apns_client:
            return self._apns_client

        if business_id:
            return create_apns_client_for_business(business_id)

        return create_apns_client()

    def generate_pass(
        self,
        customer: dict,
        design: dict,
    ) -> bytes:
        """
        Generate a .pkpass file for a customer.

        Args:
            customer: Customer data dict
            design: Card design dict

        Returns:
            The .pkpass file as bytes
        """
        business_id = customer.get("business_id")

        # Load locale from business
        primary_locale = "fr"
        if business_id:
            from app.repositories.business import BusinessRepository
            business = BusinessRepository.get_by_id(business_id)
            if business:
                primary_locale = business.get("primary_locale", "fr")

        translations = design.get("translations") or {}

        generator = self._get_pass_generator(
            business_id=business_id,
            design=design,
            primary_locale=primary_locale,
            translations=translations,
        )

        return generator.generate_pass(
            customer_id=customer["id"],
            name=customer.get("name", "Customer"),
            stamps=customer.get("stamps", 0),
            auth_token=customer["auth_token"],
            business_id=business_id,
        )

    def get_pass_url(
        self,
        customer: dict,
    ) -> str:
        """
        Get the URL to download a customer's Apple Wallet pass.

        Args:
            customer: Customer data dict

        Returns:
            URL to download the .pkpass file
        """
        base_url = get_public_base_url()
        return f"{base_url}/passes/{customer['id']}"

    async def send_update(
        self,
        customer_id: str,
        business_id: str | None = None,
    ) -> dict:
        """
        Send push notifications to update a customer's Apple Wallet pass.

        Args:
            customer_id: The customer's ID
            business_id: The business ID (for per-business cert loading)

        Returns:
            Dict with 'success' and 'failed' counts
        """
        # Get Apple push tokens for this customer
        push_tokens = WalletRegistrationRepository.get_apple_tokens(customer_id)

        if not push_tokens:
            return {"success": 0, "failed": 0, "no_devices": True}

        # Send push notifications
        apns_client = self._get_apns_client(business_id=business_id)
        return await apns_client.send_to_all_devices(push_tokens)

    def send_update_sync(
        self,
        customer_id: str,
        business_id: str | None = None,
    ) -> dict:
        """
        Synchronous wrapper for send_update.

        Use this when calling from non-async code.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a new task in the running loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.send_update(customer_id, business_id=business_id)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self.send_update(customer_id, business_id=business_id))
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.send_update(customer_id, business_id=business_id))

    async def send_update_to_all_customers(
        self,
        business_id: str,
    ) -> dict:
        """
        Send push notifications to all customers of a business.

        Used when a design is updated to refresh all passes.

        Args:
            business_id: The business ID

        Returns:
            Dict with aggregate success/failed counts
        """
        # Get all Apple registrations for this business
        registrations = WalletRegistrationRepository.get_all_apple_for_business(business_id)

        if not registrations:
            return {"success": 0, "failed": 0, "no_devices": True}

        # Collect all push tokens
        push_tokens = [r["push_token"] for r in registrations if r.get("push_token")]

        if not push_tokens:
            return {"success": 0, "failed": 0, "no_tokens": True}

        # Send push notifications with per-business certs
        apns_client = self._get_apns_client(business_id=business_id)
        return await apns_client.send_to_all_devices(push_tokens)


def create_apple_wallet_service() -> AppleWalletService:
    """Factory function to create AppleWalletService."""
    return AppleWalletService()
