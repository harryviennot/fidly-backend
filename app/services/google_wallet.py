"""
Google Wallet API client for loyalty pass management.
Handles LoyaltyClass and LoyaltyObject operations.
"""

import time
import json
import os
from typing import Optional
from dataclasses import dataclass

import jwt
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession


@dataclass
class GoogleWalletConfig:
    """Configuration for Google Wallet API."""
    issuer_id: str
    service_account_file: str
    origins: list[str]


class GoogleWalletClient:
    """Google Wallet API client for Loyalty passes."""

    BASE_URL = "https://walletobjects.googleapis.com/walletobjects/v1"
    SCOPES = ["https://www.googleapis.com/auth/wallet_object.issuer"]

    def __init__(self, config: GoogleWalletConfig):
        self.config = config
        self._session: Optional[AuthorizedSession] = None
        self._credentials = None

    def _get_credentials(self):
        """Get or create service account credentials."""
        if self._credentials is None:
            self._credentials = service_account.Credentials.from_service_account_file(
                self.config.service_account_file,
                scopes=self.SCOPES
            )
        return self._credentials

    def _get_session(self) -> AuthorizedSession:
        """Get or create authenticated session."""
        if self._session is None:
            credentials = self._get_credentials()
            self._session = AuthorizedSession(credentials)
        return self._session

    # === LoyaltyClass Operations ===

    def create_loyalty_class(self, class_id: str, class_data: dict) -> dict:
        """
        Create a new LoyaltyClass (one per business).

        Args:
            class_id: Unique ID in format "issuer_id.business_id"
            class_data: Class configuration including issuerName, programName, etc.

        Returns:
            Created class data from Google
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/loyaltyClass"

        payload = {
            "id": class_id,
            "issuerName": class_data.get("issuer_name", "Loyalty Program"),
            "programName": class_data.get("program_name", "Loyalty Card"),
            "reviewStatus": "UNDER_REVIEW",
        }

        # Add optional fields
        if class_data.get("hex_background_color"):
            payload["hexBackgroundColor"] = class_data["hex_background_color"]

        if class_data.get("program_logo"):
            payload["programLogo"] = class_data["program_logo"]

        if class_data.get("hero_image"):
            payload["heroImage"] = class_data["hero_image"]

        if class_data.get("info_module_data"):
            payload["infoModuleData"] = class_data["info_module_data"]

        if class_data.get("text_modules_data"):
            payload["textModulesData"] = class_data["text_modules_data"]

        if class_data.get("links_module_data"):
            payload["linksModuleData"] = class_data["links_module_data"]

        # Callback URL for save/delete events
        if class_data.get("callback_url"):
            payload["callbackOptions"] = {
                "url": class_data["callback_url"]
            }

        response = session.post(url, json=payload)

        if response.status_code == 409:
            # Class already exists - update instead
            print(f"Class {class_id} already exists, updating...")
            return self.update_loyalty_class(class_id, class_data)

        response.raise_for_status()
        return response.json()

    def update_loyalty_class(self, class_id: str, class_data: dict) -> dict:
        """
        Update an existing LoyaltyClass (propagates to all objects).

        Args:
            class_id: The class ID to update
            class_data: Fields to update

        Returns:
            Updated class data from Google
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/loyaltyClass/{class_id}"

        # Build patch payload with only provided fields
        payload = {}

        if class_data.get("issuer_name"):
            payload["issuerName"] = class_data["issuer_name"]

        if class_data.get("program_name"):
            payload["programName"] = class_data["program_name"]

        if class_data.get("hex_background_color"):
            payload["hexBackgroundColor"] = class_data["hex_background_color"]

        if class_data.get("program_logo"):
            payload["programLogo"] = class_data["program_logo"]

        if class_data.get("hero_image"):
            payload["heroImage"] = class_data["hero_image"]

        if class_data.get("info_module_data"):
            payload["infoModuleData"] = class_data["info_module_data"]

        if class_data.get("text_modules_data"):
            payload["textModulesData"] = class_data["text_modules_data"]

        response = session.patch(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_loyalty_class(self, class_id: str) -> Optional[dict]:
        """
        Get a LoyaltyClass by ID.

        Returns:
            Class data if found, None if not found
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/loyaltyClass/{class_id}"

        response = session.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    # === LoyaltyObject Operations ===

    def create_loyalty_object(self, object_id: str, class_id: str, object_data: dict) -> dict:
        """
        Create a new LoyaltyObject (one per customer).

        Args:
            object_id: Unique ID in format "issuer_id.customer_id"
            class_id: The parent class ID
            object_data: Object configuration including stamps, barcode, etc.

        Returns:
            Created object data from Google
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/loyaltyObject"

        payload = {
            "id": object_id,
            "classId": class_id,
            "state": "ACTIVE",
            "loyaltyPoints": {
                "balance": {
                    "int": object_data.get("stamps", 0)
                },
                "label": "Stamps"
            },
            "barcode": {
                "type": "QR_CODE",
                "value": object_data.get("customer_id", object_id.split(".")[-1]),
                "alternateText": object_data.get("customer_id", "")[:8]
            },
            "groupingInfo": {
                "groupingId": class_id  # Group all passes from same business
            }
        }

        # Add account info if available
        if object_data.get("account_name"):
            payload["accountName"] = object_data["account_name"]
        if object_data.get("account_id"):
            payload["accountId"] = object_data["account_id"]

        # Add text modules for additional info
        if object_data.get("text_modules_data"):
            payload["textModulesData"] = object_data["text_modules_data"]

        # Add messages (e.g., reward notifications)
        if object_data.get("messages"):
            payload["messages"] = object_data["messages"]

        response = session.post(url, json=payload)

        if response.status_code == 409:
            # Object already exists - update instead
            print(f"Object {object_id} already exists, updating...")
            return self.update_loyalty_object(object_id, object_data)

        response.raise_for_status()
        return response.json()

    def update_loyalty_object(
        self,
        object_id: str,
        object_data: dict,
        notify: bool = False
    ) -> dict:
        """
        Update a LoyaltyObject (specific customer's pass).

        Args:
            object_id: The object ID to update
            object_data: Data to update
            notify: If True, triggers a notification (limited to 3/24h)

        Returns:
            Updated object data from Google
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/loyaltyObject/{object_id}"

        payload = {}

        if "stamps" in object_data:
            payload["loyaltyPoints"] = {
                "balance": {"int": object_data["stamps"]},
                "label": "Stamps"
            }
            # Add notification preference if requested
            if notify:
                payload["loyaltyPoints"]["balance"]["notifyPreference"] = "NOTIFY_ON_UPDATE"

        if object_data.get("text_modules_data"):
            payload["textModulesData"] = object_data["text_modules_data"]

        if object_data.get("messages"):
            payload["messages"] = object_data["messages"]

        if object_data.get("state"):
            payload["state"] = object_data["state"]

        response = session.patch(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_loyalty_object(self, object_id: str) -> Optional[dict]:
        """
        Get a LoyaltyObject by ID.

        Returns:
            Object data if found, None if not found
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/loyaltyObject/{object_id}"

        response = session.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def add_message_to_object(
        self,
        object_id: str,
        header: str,
        body: str,
        message_id: str,
        notify: bool = True
    ) -> dict:
        """
        Add a message to a LoyaltyObject (appears on pass back).

        Args:
            object_id: The object ID
            header: Message header text
            body: Message body text
            message_id: Unique ID for this message
            notify: Whether to send push notification

        Returns:
            Updated object data
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/loyaltyObject/{object_id}/addMessage"

        payload = {
            "message": {
                "header": header,
                "body": body,
                "id": message_id,
                "messageType": "TEXT_AND_NOTIFY" if notify else "TEXT"
            }
        }

        response = session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    # === JWT Generation for "Add to Wallet" ===

    def create_save_jwt(
        self,
        object_data: dict,
        class_data: Optional[dict] = None
    ) -> str:
        """
        Create a signed JWT for the "Add to Google Wallet" button.

        This JWT contains the full object/class definition, allowing
        creation on-the-fly when the user saves to their wallet.

        Args:
            object_data: The LoyaltyObject to embed in the JWT
            class_data: Optional LoyaltyClass to embed (for first-time creation)

        Returns:
            Signed JWT string
        """
        credentials = self._get_credentials()

        claims = {
            "iss": credentials.service_account_email,
            "aud": "google",
            "origins": self.config.origins,
            "typ": "savetowallet",
            "payload": {
                "loyaltyObjects": [object_data]
            },
            "iat": int(time.time()),
        }

        # Include class definition if provided (for first-time setup)
        if class_data:
            claims["payload"]["loyaltyClasses"] = [class_data]

        # Read the private key from service account file
        with open(self.config.service_account_file, 'r') as f:
            service_account_info = json.load(f)

        # Sign with RS256 using the service account's private key
        token = jwt.encode(
            claims,
            service_account_info["private_key"],
            algorithm="RS256"
        )

        return token

    def get_save_url(self, jwt_token: str) -> str:
        """
        Get the "Add to Google Wallet" URL from a JWT.

        Args:
            jwt_token: Signed JWT from create_save_jwt()

        Returns:
            URL that users can click to add pass to wallet
        """
        return f"https://pay.google.com/gp/v/save/{jwt_token}"


def create_google_wallet_client() -> GoogleWalletClient:
    """Factory function to create GoogleWalletClient from settings."""
    from app.core.config import settings

    # Check if Google Wallet is configured
    if not settings.google_wallet_issuer_id:
        raise ValueError("Google Wallet issuer ID not configured")

    if not os.path.exists(settings.google_wallet_credentials_path):
        raise FileNotFoundError(
            f"Google Wallet credentials not found at {settings.google_wallet_credentials_path}"
        )

    config = GoogleWalletConfig(
        issuer_id=settings.google_wallet_issuer_id,
        service_account_file=settings.google_wallet_credentials_path,
        origins=[
            settings.base_url,
            settings.showcase_url,
            settings.web_app_url
        ]
    )

    return GoogleWalletClient(config)


def is_google_wallet_configured() -> bool:
    """Check if Google Wallet is properly configured."""
    from app.core.config import settings

    return bool(
        settings.google_wallet_issuer_id and
        os.path.exists(settings.google_wallet_credentials_path)
    )
