"""
Google Wallet API client for Generic pass management.
Handles GenericClass and GenericObject operations.
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
    """Google Wallet API client for Generic passes."""

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

    # === GenericClass Operations ===

    def create_generic_class(self, class_id: str, class_data: dict) -> dict:
        """
        Create a new GenericClass (one per business).

        Args:
            class_id: Unique ID in format "issuer_id.business_id"
            class_data: Class configuration

        Returns:
            Created class data from Google
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/genericClass"

        payload = {
            "id": class_id,
            "reviewStatus": "UNDER_REVIEW",
        }

        # Add links module for website
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
            return self.update_generic_class(class_id, class_data)

        response.raise_for_status()
        return response.json()

    def update_generic_class(self, class_id: str, class_data: dict) -> dict:
        """
        Update an existing GenericClass.

        Args:
            class_id: The class ID to update
            class_data: Fields to update

        Returns:
            Updated class data from Google
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/genericClass/{class_id}"

        # Build patch payload with only provided fields
        payload = {}

        if class_data.get("links_module_data"):
            payload["linksModuleData"] = class_data["links_module_data"]

        response = session.patch(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_generic_class(self, class_id: str) -> Optional[dict]:
        """
        Get a GenericClass by ID.

        Returns:
            Class data if found, None if not found
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/genericClass/{class_id}"

        response = session.get(url)
        # Google returns 404 or 400 when class doesn't exist
        if response.status_code in (404, 400):
            return None
        response.raise_for_status()
        return response.json()

    # === GenericObject Operations ===

    def create_generic_object(self, object_id: str, class_id: str, object_data: dict) -> dict:
        """
        Create a new GenericObject (one per customer).

        Args:
            object_id: Unique ID in format "issuer_id.customer_id"
            class_id: The parent class ID
            object_data: Object configuration

        Returns:
            Created object data from Google
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/genericObject"

        payload = {
            "id": object_id,
            "classId": class_id,
            "state": "ACTIVE",
            "genericType": "GENERIC_TYPE_UNSPECIFIED",
            # Required: cardTitle (business name)
            "cardTitle": {
                "defaultValue": {
                    "language": "en",
                    "value": object_data.get("business_name", "Loyalty Card")
                }
            },
            # Required: header (pass title)
            "header": {
                "defaultValue": {
                    "language": "en",
                    "value": object_data.get("card_title", "Stamp Card")
                }
            },
            "barcode": {
                "type": "QR_CODE",
                "value": object_data.get("customer_id", object_id.split(".")[-1]),
                "alternateText": object_data.get("customer_id", "")[:8]
            },
            "groupingInfo": {
                "groupingId": class_id
            }
        }

        # Subheader for stamp progress
        if object_data.get("subheader"):
            payload["subheader"] = {
                "defaultValue": {
                    "language": "en",
                    "value": object_data["subheader"]
                }
            }

        # Background color
        if object_data.get("hex_background_color"):
            payload["hexBackgroundColor"] = object_data["hex_background_color"]

        # Logo
        if object_data.get("logo"):
            payload["logo"] = object_data["logo"]

        # Hero image (per-customer!)
        if object_data.get("hero_image"):
            payload["heroImage"] = object_data["hero_image"]

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
            return self.update_generic_object(object_id, object_data)

        response.raise_for_status()
        return response.json()

    def update_generic_object(
        self,
        object_id: str,
        object_data: dict,
        notify: bool = False
    ) -> dict:
        """
        Update a GenericObject (specific customer's pass).

        Args:
            object_id: The object ID to update
            object_data: Data to update
            notify: If True, triggers a notification (limited to 3/24h)

        Returns:
            Updated object data from Google
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/genericObject/{object_id}"

        payload = {}

        # Update subheader with stamp progress
        if object_data.get("subheader"):
            payload["subheader"] = {
                "defaultValue": {
                    "language": "en",
                    "value": object_data["subheader"]
                }
            }

        if object_data.get("text_modules_data"):
            payload["textModulesData"] = object_data["text_modules_data"]

        if object_data.get("messages"):
            payload["messages"] = object_data["messages"]

        if object_data.get("state"):
            payload["state"] = object_data["state"]

        # Per-customer hero image
        if object_data.get("hero_image"):
            payload["heroImage"] = object_data["hero_image"]

        # Notification via messages
        if notify and object_data.get("notification_message"):
            if "messages" not in payload:
                payload["messages"] = []
            payload["messages"].append({
                "header": "Update",
                "body": object_data["notification_message"],
                "id": f"notify_{int(time.time())}",
                "messageType": "TEXT_AND_NOTIFY"
            })

        print(f"Google Wallet API: PATCH {url}")
        print(f"Google Wallet API: Payload = {payload}")

        response = session.patch(url, json=payload)
        print(f"Google Wallet API: Response status = {response.status_code}")

        # Log error details if request failed
        if response.status_code >= 400:
            error_text = response.text
            print(f"Google Wallet API: Error response = {error_text}")
            # Raise with the full error response included so callers can handle specific errors
            raise Exception(f"Google Wallet API error ({response.status_code}): {error_text}")

        return response.json()

    # === Delete Operations ===

    def delete_object(self, object_id: str, object_type: str = "generic") -> bool:
        """
        Delete a wallet object (generic or loyalty).

        Args:
            object_id: The object ID to delete
            object_type: "generic" or "loyalty"

        Returns:
            True if deleted, False if not found
        """
        session = self._get_session()
        endpoint = "genericObject" if object_type == "generic" else "loyaltyObject"
        url = f"{self.BASE_URL}/{endpoint}/{object_id}"

        print(f"Google Wallet API: DELETE {url}")
        response = session.delete(url)
        print(f"Google Wallet API: Response status = {response.status_code}")

        if response.status_code == 404:
            return False
        if response.status_code >= 400:
            print(f"Google Wallet API: Error response = {response.text}")
        response.raise_for_status()
        return True

    # === Legacy LoyaltyObject Support ===

    def update_loyalty_object(
        self,
        object_id: str,
        object_data: dict,
        notify: bool = False
    ) -> dict:
        """
        Update a legacy LoyaltyObject (for backwards compatibility).

        Used for passes that were created before migration to Generic passes.
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/loyaltyObject/{object_id}"

        payload = {}

        if "stamps" in object_data:
            payload["loyaltyPoints"] = {
                "balance": {"int": object_data["stamps"]},
                "label": "Stamps"
            }
            if notify:
                payload["loyaltyPoints"]["balance"]["notifyPreference"] = "NOTIFY_ON_UPDATE"

        if object_data.get("text_modules_data"):
            payload["textModulesData"] = object_data["text_modules_data"]

        if object_data.get("messages"):
            payload["messages"] = object_data["messages"]

        print(f"Google Wallet API (legacy): PATCH {url}")
        print(f"Google Wallet API (legacy): Payload = {payload}")

        response = session.patch(url, json=payload)
        print(f"Google Wallet API (legacy): Response status = {response.status_code}")

        if response.status_code >= 400:
            print(f"Google Wallet API (legacy): Error response = {response.text}")

        response.raise_for_status()
        return response.json()

    def get_generic_object(self, object_id: str) -> Optional[dict]:
        """
        Get a GenericObject by ID.

        Returns:
            Object data if found, None if not found
        """
        session = self._get_session()
        url = f"{self.BASE_URL}/genericObject/{object_id}"

        response = session.get(url)
        # Google returns 404 or 400 when object doesn't exist
        if response.status_code in (404, 400):
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
        Add a message to a GenericObject (appears on pass back).

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
        url = f"{self.BASE_URL}/genericObject/{object_id}/addMessage"

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
            object_data: The GenericObject to embed in the JWT
            class_data: Optional GenericClass to embed (for first-time creation)

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
                "genericObjects": [object_data]
            },
            "iat": int(time.time()),
        }

        # Include class definition if provided (for first-time setup)
        if class_data:
            claims["payload"]["genericClasses"] = [class_data]

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
