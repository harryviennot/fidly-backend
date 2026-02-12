"""
Demo Google Wallet service for interactive landing page demo.
Uses fixed Stampeo branding and generates save URLs for Google Wallet.
"""

import logging
import time
from typing import Optional

import httpx
from google.auth import jwt as google_jwt
from google.oauth2 import service_account

from app.core.config import settings, get_public_base_url

logger = logging.getLogger(__name__)


# Stampeo demo branding colors (same as Apple demo)
DEMO_BLACK = "#1c1c1e"  # Stampeo black background
DEMO_WHITE = "#ffffff"
DEMO_ORANGE = "#f97316"  # Accent orange
DEMO_TOTAL_STAMPS = 8

# Pre-generated assets stored in Supabase Storage
DEMO_HERO_PATH = "stampeo/demo/strips/google"
DEMO_LOGO_PATH = "stampeo/demo/logo.png"

# Bilingual strings for demo pass (French primary, English translation)
DEMO_STRINGS = {
    "stamps_header": {"fr": "TAMPONS", "en": "STAMPS"},
    "reward_header": {"fr": "RÉCOMPENSE", "en": "REWARD"},
    "reward_completed": {"fr": "30 jours gratuits !", "en": "30 days free!"},
    "reward_pending": {"fr": "30 jours d'essai gratuit", "en": "30 days free trial"},
    "location_header": {"fr": "Adresse", "en": "Location"},
    "location_body": {"fr": "123 Rue Principale, Paris 75001", "en": "123 Main Street, Paris 75001"},
    "hours_header": {"fr": "Horaires", "en": "Opening Hours"},
    "hours_body": {"fr": "Lun-Ven : 8h-19h, Sam-Dim : 9h-17h", "en": "Mon-Fri: 8am-7pm, Sat-Sun: 9am-5pm"},
    "website_header": {"fr": "Site web", "en": "Website"},
    "contact_header": {"fr": "Contact", "en": "Contact"},
    "phone_header": {"fr": "Téléphone", "en": "Phone"},
    "card_title": {"fr": "Stampeo", "en": "Stampeo"},
    "card_header": {"fr": "Carte Démo Interactive", "en": "Interactive Demo Card"},
    "hero_desc": {"fr": "{stamps}/{total} tampons", "en": "{stamps}/{total} stamps"},
    "logo_desc": {"fr": "Logo Stampeo", "en": "Stampeo logo"},
    "link_desc": {"fr": "Visiter Stampeo", "en": "Visit Stampeo"},
}


class DemoGoogleWalletService:
    """
    Google Wallet service specifically for demo passes with fixed Stampeo branding.

    Generates JWT-signed save URLs that allow users to add demo passes
    to Google Wallet without prior object creation.
    """

    WALLET_API_BASE = "https://walletobjects.googleapis.com/walletobjects/v1"
    SAVE_URL_BASE = "https://pay.google.com/gp/v/save"

    # Demo-specific class ID suffix
    DEMO_CLASS_SUFFIX = "stampeo-demo"

    def __init__(
        self,
        credentials_path: str,
        issuer_id: str,
        base_url: str,
        callback_url: str,
    ):
        self.issuer_id = issuer_id
        self.base_url = base_url.rstrip("/")
        self.callback_url = callback_url

        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/wallet_object.issuer"]
        )
        self._http_client: Optional[httpx.Client] = None

    @property
    def http_client(self) -> httpx.Client:
        """Lazy-initialize HTTP client with auth."""
        if self._http_client is None:
            from google.auth.transport.requests import Request
            self.credentials.refresh(Request())

            self._http_client = httpx.Client(
                headers={
                    "Authorization": f"Bearer {self.credentials.token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._http_client

    @staticmethod
    def _demo_localized(fr_value: str, en_value: str) -> dict:
        """Build a Google Wallet localizedString with French default and English translation."""
        result: dict = {
            "defaultValue": {"language": "fr", "value": fr_value}
        }
        if fr_value != en_value:
            result["translatedValues"] = [{"language": "en", "value": en_value}]
        return result

    def _get_class_id(self) -> str:
        """Get the demo class ID."""
        return f"{self.issuer_id}.{self.DEMO_CLASS_SUFFIX}"

    def _get_object_id(self, customer_id: str) -> str:
        """Generate object ID for a demo customer."""
        return f"{self.issuer_id}.demo-{customer_id}"

    def _get_hero_url(self, stamp_count: int) -> str:
        """Get pre-generated hero image URL for a stamp count."""
        # Clamp to valid range
        stamp_count = max(0, min(stamp_count, DEMO_TOTAL_STAMPS))
        return f"{settings.supabase_url}/storage/v1/object/public/businesses/{DEMO_HERO_PATH}/hero_{stamp_count}.png"

    def _get_logo_url(self) -> str:
        """Get the Stampeo demo logo URL."""
        return f"{settings.supabase_url}/storage/v1/object/public/businesses/{DEMO_LOGO_PATH}"

    def _build_demo_class_payload(self) -> dict:
        """
        Build GenericClass payload with fixed Stampeo demo branding.
        """
        class_id = self._get_class_id()

        return {
            "id": class_id,
            "classTemplateInfo": {
                "cardTemplateOverride": {
                    "cardRowTemplateInfos": [
                        # Row 1: Stamps
                        {
                            "oneItem": {
                                "item": {
                                    "firstValue": {
                                        "fields": [
                                            {"fieldPath": "object.textModulesData['stamps']"}
                                        ]
                                    }
                                }
                            }
                        },
                        # Row 2: Reward
                        {
                            "oneItem": {
                                "item": {
                                    "firstValue": {
                                        "fields": [
                                            {"fieldPath": "object.textModulesData['reward']"}
                                        ]
                                    }
                                }
                            }
                        }
                    ]
                }
            },
            "imageModulesDataMainImageUriDescription": "Stampeo Demo",
            "linksModuleData": {
                "uris": [
                    {
                        "uri": "https://stampeo.app",
                        "description": DEMO_STRINGS["link_desc"]["fr"],
                        "localizedDescription": self._demo_localized(
                            DEMO_STRINGS["link_desc"]["fr"],
                            DEMO_STRINGS["link_desc"]["en"],
                        ),
                        "id": "website",
                    }
                ]
            },
            "enableSmartTap": False,
            "hexBackgroundColor": DEMO_BLACK,
            "callbackOptions": {
                "url": self.callback_url,
                "updateRequestUrl": self.callback_url,
            },
        }

    def _build_demo_object_payload(
        self,
        customer_id: str,
        stamp_count: int,
    ) -> dict:
        """
        Build GenericObject payload for a demo customer.

        Uses pre-generated hero images from Supabase Storage.
        French as default language, English via translatedValues.
        """
        S = DEMO_STRINGS
        L = self._demo_localized
        class_id = self._get_class_id()
        object_id = self._get_object_id(customer_id)

        # Determine reward text
        if stamp_count >= DEMO_TOTAL_STAMPS:
            reward_fr = S["reward_completed"]["fr"]
            reward_en = S["reward_completed"]["en"]
        else:
            reward_fr = S["reward_pending"]["fr"]
            reward_en = S["reward_pending"]["en"]

        text_modules = [
            {
                "id": "stamps",
                "header": S["stamps_header"]["fr"],
                "localizedHeader": L(S["stamps_header"]["fr"], S["stamps_header"]["en"]),
                "body": f"{stamp_count} / {DEMO_TOTAL_STAMPS}",
            },
            {
                "id": "reward",
                "header": S["reward_header"]["fr"],
                "localizedHeader": L(S["reward_header"]["fr"], S["reward_header"]["en"]),
                "body": reward_fr,
                "localizedBody": L(reward_fr, reward_en),
            },
            # Back fields (shown in details section)
            {
                "id": "location",
                "header": S["location_header"]["fr"],
                "localizedHeader": L(S["location_header"]["fr"], S["location_header"]["en"]),
                "body": S["location_body"]["fr"],
                "localizedBody": L(S["location_body"]["fr"], S["location_body"]["en"]),
            },
            {
                "id": "hours",
                "header": S["hours_header"]["fr"],
                "localizedHeader": L(S["hours_header"]["fr"], S["hours_header"]["en"]),
                "body": S["hours_body"]["fr"],
                "localizedBody": L(S["hours_body"]["fr"], S["hours_body"]["en"]),
            },
            {
                "id": "website",
                "header": S["website_header"]["fr"],
                "localizedHeader": L(S["website_header"]["fr"], S["website_header"]["en"]),
                "body": "www.stampeo.app",
            },
            {
                "id": "contact",
                "header": S["contact_header"]["fr"],
                "localizedHeader": L(S["contact_header"]["fr"], S["contact_header"]["en"]),
                "body": "harry.viennot@icloud.com",
            },
            {
                "id": "phone",
                "header": S["phone_header"]["fr"],
                "localizedHeader": L(S["phone_header"]["fr"], S["phone_header"]["en"]),
                "body": "06 49 37 04 70",
            },
        ]

        # Get pre-generated image URLs
        hero_url = self._get_hero_url(stamp_count)
        logo_url = self._get_logo_url()

        hero_fr = S["hero_desc"]["fr"].format(stamps=stamp_count, total=DEMO_TOTAL_STAMPS)
        hero_en = S["hero_desc"]["en"].format(stamps=stamp_count, total=DEMO_TOTAL_STAMPS)
        logo_content_description = L(S["logo_desc"]["fr"], S["logo_desc"]["en"])

        return {
            "id": object_id,
            "classId": class_id,
            "state": "ACTIVE",
            "textModulesData": text_modules,
            "heroImage": {
                "sourceUri": {"uri": hero_url},
                "contentDescription": L(hero_fr, hero_en),
            },
            "logo": {
                "sourceUri": {"uri": logo_url},
                "contentDescription": logo_content_description,
            },
            "wideLogo": {
                "sourceUri": {"uri": logo_url},
                "contentDescription": logo_content_description,
            },
            "cardTitle": L(S["card_title"]["fr"], S["card_title"]["en"]),
            "header": L(S["card_header"]["fr"], S["card_header"]["en"]),
            "hexBackgroundColor": DEMO_BLACK,
            "barcode": {
                "type": "QR_CODE",
                "value": customer_id,
            },
        }

    def generate_save_url(
        self,
        customer_id: str,
        stamp_count: int = 0,
    ) -> str:
        """
        Generate a JWT-signed save URL for Google Wallet.

        The URL allows the user to add the demo pass to their Google Wallet
        by clicking it. No prior object creation needed.
        """
        object_payload = self._build_demo_object_payload(customer_id, stamp_count)
        class_payload = self._build_demo_class_payload()

        claims = {
            "iss": self.credentials.service_account_email,
            "aud": "google",
            "typ": "savetowallet",
            "iat": int(time.time()),
            "origins": [self.base_url, "https://stampeo.app"],
            "payload": {
                "genericClasses": [class_payload],
                "genericObjects": [object_payload],
            }
        }

        token = google_jwt.encode(self.credentials._signer, claims).decode("utf-8")
        return f"{self.SAVE_URL_BASE}/{token}"

    def update_demo_object(
        self,
        customer_id: str,
        stamp_count: int,
    ) -> bool:
        """
        Update an existing demo Google Wallet object with new stamp count.

        Returns True if update succeeded or object doesn't exist.
        """
        object_id = self._get_object_id(customer_id)
        payload = self._build_demo_object_payload(customer_id, stamp_count)

        try:
            response = self.http_client.patch(
                f"{self.WALLET_API_BASE}/genericObject/{object_id}",
                json=payload,
            )

            if response.status_code == 404:
                # Object doesn't exist (user never saved the pass)
                logger.info(f"[Demo Google] Object {object_id} not found, skipping update")
                return True

            if response.status_code not in (200, 201):
                logger.error(
                    f"[Demo Google] Update failed: {response.status_code} - {response.text}"
                )
                return False

            logger.info(f"[Demo Google] Updated object {object_id} to {stamp_count} stamps")
            return True

        except Exception as e:
            logger.error(f"[Demo Google] Update error: {e}")
            return False

    def handle_callback(self, callback_data: dict) -> dict:
        """
        Process a Google Wallet callback for demo passes.

        Returns dict with action and customer_id.
        """
        event_type = callback_data.get("eventType", "")
        object_id = callback_data.get("objectId", "")

        # Extract customer_id from object_id (format: issuerId.demo-customerId)
        customer_id = None
        if object_id and ".demo-" in object_id:
            customer_id = object_id.split(".demo-", 1)[1]

        return {
            "action": event_type,
            "customer_id": customer_id,
            "object_id": object_id,
        }

    def ensure_class_exists(self) -> bool:
        """
        Ensure the demo class exists with correct callback URL.

        Creates the class if it doesn't exist, or updates it if callback URL changed.
        This is needed because the JWT approach doesn't update existing classes.

        Returns True if successful.
        """
        class_id = self._get_class_id()
        class_payload = self._build_demo_class_payload()

        try:
            # Try to get existing class
            response = self.http_client.get(
                f"{self.WALLET_API_BASE}/genericClass/{class_id}"
            )

            if response.status_code == 404:
                # Class doesn't exist, create it
                logger.info(f"[Demo Google] Creating class {class_id}")
                create_response = self.http_client.post(
                    f"{self.WALLET_API_BASE}/genericClass",
                    json=class_payload,
                )
                if create_response.status_code not in (200, 201):
                    logger.error(f"[Demo Google] Failed to create class: {create_response.text}")
                    return False
                logger.info(f"[Demo Google] Class created with callback: {self.callback_url}")
                return True

            if response.status_code == 200:
                # Class exists, check if callback URL needs updating
                existing = response.json()
                existing_callback = existing.get("callbackOptions", {}).get("url", "")

                if existing_callback != self.callback_url:
                    logger.info(f"[Demo Google] Updating class callback from {existing_callback} to {self.callback_url}")
                    update_response = self.http_client.patch(
                        f"{self.WALLET_API_BASE}/genericClass/{class_id}",
                        json=class_payload,
                    )
                    if update_response.status_code not in (200, 201):
                        logger.error(f"[Demo Google] Failed to update class: {update_response.text}")
                        return False
                    logger.info("[Demo Google] Class callback updated successfully")
                return True

            logger.error(f"[Demo Google] Unexpected response: {response.status_code}")
            return False

        except Exception as e:
            logger.error(f"[Demo Google] Error ensuring class exists: {e}")
            return False

    def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None


def create_demo_google_wallet_service() -> DemoGoogleWalletService:
    """Factory function to create DemoGoogleWalletService."""
    # Use public URL (tunnel if available, otherwise base_url)
    public_url = get_public_base_url()
    callback_url = f"{public_url}/demo/google-wallet/callback"

    return DemoGoogleWalletService(
        credentials_path=settings.google_wallet_credentials_path,
        issuer_id=settings.google_wallet_issuer_id,
        base_url=public_url,
        callback_url=callback_url,
    )
