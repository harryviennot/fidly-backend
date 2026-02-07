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

from app.core.config import settings

logger = logging.getLogger(__name__)


# Stampeo demo branding colors (same as Apple demo)
DEMO_BLACK = "#1c1c1e"  # Stampeo black background
DEMO_WHITE = "#ffffff"
DEMO_ORANGE = "#f97316"  # Accent orange
DEMO_TOTAL_STAMPS = 8


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

    def _get_class_id(self) -> str:
        """Get the demo class ID."""
        return f"{self.issuer_id}.{self.DEMO_CLASS_SUFFIX}"

    def _get_object_id(self, customer_id: str) -> str:
        """Generate object ID for a demo customer."""
        return f"{self.issuer_id}.demo-{customer_id}"

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
                        "description": "Visit Stampeo",
                        "id": "website"
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

        Uses in-memory stamp visualization via textModulesData
        rather than pre-generated hero images.
        """
        class_id = self._get_class_id()
        object_id = self._get_object_id(customer_id)

        # Create visual stamp progress (using emoji for now)
        filled = stamp_count
        empty = DEMO_TOTAL_STAMPS - stamp_count
        stamp_visual = "🟠" * filled + "⚫" * empty

        # Determine reward text
        if stamp_count >= DEMO_TOTAL_STAMPS:
            reward_text = "🎁 30 days free!"
        else:
            reward_text = "30 days free trial"

        text_modules = [
            {
                "id": "stamps",
                "header": "STAMPS",
                "body": f"{stamp_count} / {DEMO_TOTAL_STAMPS}  {stamp_visual}",
            },
            {
                "id": "reward",
                "header": "REWARD",
                "body": reward_text,
            },
            # Back fields (shown in details section)
            {
                "id": "location",
                "header": "Location",
                "body": "123 Main Street, Paris 75001",
            },
            {
                "id": "hours",
                "header": "Opening Hours",
                "body": "Mon-Fri: 8am-7pm, Sat-Sun: 9am-5pm",
            },
            {
                "id": "website",
                "header": "Website",
                "body": "www.stampeo.app",
            },
            {
                "id": "contact",
                "header": "Contact",
                "body": "harry@stampeo.app",
            },
        ]

        return {
            "id": object_id,
            "classId": class_id,
            "state": "ACTIVE",
            "textModulesData": text_modules,
            "cardTitle": {
                "defaultValue": {
                    "language": "en",
                    "value": "Stampeo"
                }
            },
            "header": {
                "defaultValue": {
                    "language": "en",
                    "value": "Interactive Demo Card"
                }
            },
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

    def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None


def create_demo_google_wallet_service() -> DemoGoogleWalletService:
    """Factory function to create DemoGoogleWalletService."""
    # Build callback URL for demo
    callback_url = f"{settings.base_url}/demo/google-wallet/callback"

    return DemoGoogleWalletService(
        credentials_path=settings.google_wallet_credentials_path,
        issuer_id=settings.google_wallet_issuer_id,
        base_url=settings.base_url,
        callback_url=callback_url,
    )
