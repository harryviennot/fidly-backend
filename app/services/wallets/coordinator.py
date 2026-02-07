"""
Pass Coordinator for unified wallet operations.

Orchestrates operations across Apple and Google Wallet services,
handling common workflows like customer registration and stamp updates.
"""

import asyncio
import logging
from typing import Optional

from app.core.config import get_public_base_url

logger = logging.getLogger(__name__)
from app.repositories.customer import CustomerRepository
from app.repositories.card_design import CardDesignRepository
from app.repositories.business import BusinessRepository
from app.repositories.wallet_registration import WalletRegistrationRepository
from app.services.wallets.apple import AppleWalletService, create_apple_wallet_service
from app.services.wallets.google import GoogleWalletService, create_google_wallet_service
from app.services.wallets.strips import StripImageService, create_strip_image_service


class PassCoordinator:
    """
    Coordinates operations across Apple and Google Wallet services.

    Provides a unified interface for common wallet operations:
    - Customer creation (generate wallet URLs)
    - Stamp updates (notify both wallets)
    - Design updates (regenerate strips, update classes/objects)
    """

    def __init__(
        self,
        apple: Optional[AppleWalletService] = None,
        google: Optional[GoogleWalletService] = None,
        strips: Optional[StripImageService] = None,
    ):
        self._apple = apple
        self._google = google
        self._strips = strips

    @property
    def apple(self) -> AppleWalletService:
        """Lazy-initialize Apple Wallet service."""
        if self._apple is None:
            self._apple = create_apple_wallet_service()
        return self._apple

    @property
    def google(self) -> GoogleWalletService:
        """Lazy-initialize Google Wallet service."""
        if self._google is None:
            self._google = create_google_wallet_service()
        return self._google

    @property
    def strips(self) -> StripImageService:
        """Lazy-initialize Strip Image service."""
        if self._strips is None:
            self._strips = create_strip_image_service()
        return self._strips

    def get_wallet_urls(
        self,
        customer: dict,
        business: dict,
        design: dict,
    ) -> dict:
        """
        Get wallet save URLs for both platforms.

        Returns:
            Dict with 'apple_url' and 'google_url' keys
        """
        stamp_count = customer.get("stamps", 0)

        # Apple Wallet URL (pass download endpoint)
        apple_url = self.apple.get_pass_url(customer)

        # Google Wallet URL (JWT-signed save URL)
        try:
            google_url = self.google.generate_save_url(
                customer=customer,
                business=business,
                design=design,
                stamp_count=stamp_count,
            )
        except Exception as e:
            print(f"Error generating Google Wallet URL: {e}")
            google_url = None

        return {
            "apple_url": apple_url,
            "google_url": google_url,
        }

    def on_customer_created(
        self,
        customer: dict,
        business: dict,
        design: dict,
    ) -> dict:
        """
        Handle customer creation - generate wallet URLs.

        Called after a new customer is created. Returns URLs for both
        Apple and Google Wallet so the customer can add the pass.

        Args:
            customer: The newly created customer dict
            business: The business dict
            design: The active card design dict

        Returns:
            Dict with wallet URLs
        """
        return self.get_wallet_urls(customer, business, design)

    async def on_stamp_added(
        self,
        customer: dict,
        business: dict,
        design: dict,
    ) -> dict:
        """
        Handle stamp addition - update both wallets.

        Called after stamps are added to a customer. Sends push
        notifications to Apple Wallet and updates Google Wallet object.

        Args:
            customer: The updated customer dict (with new stamp count)
            business: The business dict
            design: The active card design dict

        Returns:
            Dict with update results for both platforms
        """
        customer_id = customer["id"]
        stamp_count = customer.get("stamps", 0)

        results = {
            "apple": None,
            "google": None,
        }

        # Update Apple Wallet (via push notification)
        # Apple requires registration because we need the device push token
        if WalletRegistrationRepository.has_apple_wallet(customer_id):
            try:
                results["apple"] = await self.apple.send_update(customer_id)
            except Exception as e:
                logger.error(f"[PassCoordinator] Apple Wallet update error: {e}")
                results["apple"] = {"error": str(e)}

        # Update Google Wallet object
        # Unlike Apple, we don't need registration because Google object IDs are
        # deterministic ({issuerId}.{customerId}). We always try to update since
        # Google callbacks can be unreliable and the pass might exist without
        # a registration in our database.
        try:
            self.google.update_object(
                customer=customer,
                business=business,
                design=design,
                stamp_count=stamp_count,
            )
            results["google"] = {"success": True}
        except Exception as e:
            logger.error(f"[PassCoordinator] Google Wallet update error: {e}")
            results["google"] = {"error": str(e)}

        return results

    def on_stamp_added_sync(
        self,
        customer: dict,
        business: dict,
        design: dict,
    ) -> dict:
        """Synchronous wrapper for on_stamp_added."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.on_stamp_added(customer, business, design)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.on_stamp_added(customer, business, design)
                )
        except RuntimeError:
            return asyncio.run(self.on_stamp_added(customer, business, design))

    async def on_design_updated(
        self,
        business: dict,
        design: dict,
        regenerate_strips: bool = True,
    ) -> dict:
        """
        Handle design update - update all customer passes.

        Called after a card design is updated. If strips need regeneration,
        regenerates them first, then notifies all customers.

        Args:
            business: The business dict
            design: The updated design dict
            regenerate_strips: Whether to regenerate strip images

        Returns:
            Dict with update results
        """
        results = {
            "strips_regenerated": False,
            "google_class_updated": False,
            "apple_notifications": None,
            "google_objects_updated": 0,
        }

        business_id = business["id"]

        # Regenerate strip images if needed
        if regenerate_strips:
            try:
                self.strips.delete_strips_for_design(design["id"])
                self.strips.pregenerate_all_strips(design, business_id)
                results["strips_regenerated"] = True
            except Exception as e:
                print(f"Strip regeneration error: {e}")

        # Update Google Wallet class
        try:
            self.google.create_or_update_class(business, design)
            results["google_class_updated"] = True
        except Exception as e:
            print(f"Google class update error: {e}")

        # Notify all Apple Wallet customers
        try:
            results["apple_notifications"] = await self.apple.send_update_to_all_customers(
                business_id
            )
        except Exception as e:
            print(f"Apple notifications error: {e}")
            results["apple_notifications"] = {"error": str(e)}

        # Update all Google Wallet objects
        google_registrations = WalletRegistrationRepository.get_all_google_for_business(
            business_id
        )

        for reg in google_registrations:
            try:
                customer_id = reg["customer_id"]
                customer = CustomerRepository.get_by_id(customer_id)
                if customer:
                    self.google.update_object(
                        customer=customer,
                        business=business,
                        design=design,
                        stamp_count=customer.get("stamps", 0),
                    )
                    results["google_objects_updated"] += 1
            except Exception as e:
                print(f"Google object update error for {customer_id}: {e}")

        return results

    def on_design_activated(
        self,
        business: dict,
        design: dict,
    ) -> dict:
        """
        Handle design activation.

        Called when a design is activated. Strips should already exist
        from creation. Just update the Google class and notify customers.

        Args:
            business: The business dict
            design: The activated design dict

        Returns:
            Dict with update results
        """
        results = {
            "google_class_updated": False,
            "strips_exist": False,
        }

        # Verify strips exist
        results["strips_exist"] = self.strips.strips_exist_for_design(design["id"])

        if not results["strips_exist"]:
            # Strips don't exist, generate them now (shouldn't happen normally)
            print(f"Warning: Strips missing for design {design['id']}, generating...")
            try:
                self.strips.pregenerate_all_strips(design, business["id"])
                results["strips_exist"] = True
            except Exception as e:
                print(f"Strip generation error: {e}")

        # Update Google Wallet class with new design
        try:
            self.google.create_or_update_class(business, design)
            results["google_class_updated"] = True
        except Exception as e:
            print(f"Google class update error: {e}")

        return results

    def pregenerate_strips_for_design(
        self,
        design: dict,
        business_id: str,
    ) -> dict:
        """
        Pre-generate strip images for a design.

        Called synchronously when a design is created.

        Args:
            design: The design dict
            business_id: The business ID

        Returns:
            Dict with generated strip URLs
        """
        return self.strips.pregenerate_all_strips(design, business_id)


def create_pass_coordinator() -> PassCoordinator:
    """Factory function to create PassCoordinator."""
    return PassCoordinator()
