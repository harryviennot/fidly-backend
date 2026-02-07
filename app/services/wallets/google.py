"""
Google Wallet Service for Generic Pass management.

Uses Generic Pass (not Loyalty Pass) to allow per-customer hero images
that display dynamic stamp counts.
"""

import logging
import time
from typing import Optional

import httpx
from google.auth import jwt as google_jwt
from google.oauth2 import service_account

from app.core.config import settings, get_callback_url, get_public_base_url
from app.repositories.wallet_registration import WalletRegistrationRepository
from app.repositories.strip_image import StripImageRepository

logger = logging.getLogger(__name__)


class GoogleWalletService:
    """
    Service for creating and managing Google Wallet Generic Passes.

    Architecture:
    - One GenericClass per BUSINESS (shared template)
    - One GenericObject per CUSTOMER (with individual hero image)
    - Hero image URL points to pre-generated strips in Supabase Storage
    """

    WALLET_API_BASE = "https://walletobjects.googleapis.com/walletobjects/v1"
    SAVE_URL_BASE = "https://pay.google.com/gp/v/save"

    def __init__(
        self,
        credentials_path: str,
        issuer_id: str,
    ):
        self.issuer_id = issuer_id
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/wallet_object.issuer"]
        )
        self._http_client: Optional[httpx.Client] = None

    @property
    def http_client(self) -> httpx.Client:
        """Lazy-initialize HTTP client with auth."""
        if self._http_client is None:
            # Refresh credentials to get access token
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

    def _get_class_id(self, business_id: str) -> str:
        """Generate class ID for a business."""
        return f"{self.issuer_id}.{business_id}"

    def _get_object_id(self, customer_id: str) -> str:
        """Generate object ID for a customer."""
        return f"{self.issuer_id}.{customer_id}"

    def _build_class_payload(
        self,
        business: dict,
        design: dict,
    ) -> dict:
        """
        Build GenericClass payload for Google Wallet API.

        The class is shared by all customers of a business.
        """
        class_id = self._get_class_id(business["id"])
        callback_url = get_callback_url()

        # Parse background color for card
        bg_color = design.get("background_color", "rgb(139, 90, 43)")
        hex_color = self._rgb_to_hex(bg_color)

        # Build dynamic card row template based on design fields
        card_rows = self._build_card_row_template_infos(design)

        payload = {
            "id": class_id,
            "classTemplateInfo": {
                "cardTemplateOverride": {
                    "cardRowTemplateInfos": card_rows
                }
            },
            "imageModulesDataMainImageUriDescription": "Loyalty Progress",
            "linksModuleData": {
                "uris": [
                    {
                        "uri": f"{get_public_base_url()}/business/{business['id']}",
                        "description": "View Loyalty Card",
                        "id": "website"
                    }
                ]
            },
            "enableSmartTap": False,
            "hexBackgroundColor": hex_color,
            "callbackOptions": {
                "url": callback_url,
                "updateRequestUrl": callback_url,
            },
        }

        # Only add heroImage if we have a valid logo URL
        logo_url = design.get("logo_url")
        if logo_url:
            payload["heroImage"] = {
                "sourceUri": {"uri": logo_url},
                "contentDescription": {
                    "defaultValue": {
                        "language": "en",
                        "value": f"{business.get('name', 'Business')} Loyalty Card"
                    }
                }
            }

        return payload

    def _build_object_payload(
        self,
        customer: dict,
        business: dict,
        design: dict,
        stamp_count: int,
    ) -> dict:
        """
        Build GenericObject payload for Google Wallet API.

        Each customer has their own object with a unique hero image
        showing their current stamp count.
        """
        class_id = self._get_class_id(business["id"])
        object_id = self._get_object_id(customer["id"])

        # Get pre-generated hero image URL from strip_images table
        hero_url = StripImageRepository.get_google_hero_url(
            design_id=design["id"],
            stamp_count=stamp_count,
        )

        total_stamps = design.get("total_stamps", 10)
        description = design.get("description", "Loyalty Card")

        # Parse colors
        bg_color = design.get("background_color", "rgb(139, 90, 43)")
        hex_color = self._rgb_to_hex(bg_color)

        # Build textModulesData - stamps first, then design fields
        text_modules = [
            {
                "id": "stamps",
                "header": "STAMPS",
                "body": f"{stamp_count} / {total_stamps}",
            }
        ]

        # Secondary fields (displayed on card front - row 2)
        secondary_fields = design.get("secondary_fields", [])
        text_modules.extend(
            self._convert_pass_fields_to_text_modules(secondary_fields, "sec_")
        )

        # Auxiliary fields (displayed on card front - one row)
        auxiliary_fields = design.get("auxiliary_fields", [])
        text_modules.extend(
            self._convert_pass_fields_to_text_modules(auxiliary_fields, "aux_")
        )

        # Back fields (displayed in details section only - not in cardRowTemplateInfos)
        back_fields = design.get("back_fields", [])
        text_modules.extend(
            self._convert_pass_fields_to_text_modules(back_fields, "back_")
        )

        payload = {
            "id": object_id,
            "classId": class_id,
            "state": "ACTIVE",
            "textModulesData": text_modules,
            "cardTitle": {
                "defaultValue": {
                    "language": "en",
                    "value": business.get("name", "Loyalty Card")
                }
            },
            "header": {
                "defaultValue": {
                    "language": "en",
                    "value": description
                }
            },
            "hexBackgroundColor": hex_color,
            "barcode": {
                "type": "QR_CODE",
                "value": customer["id"],
            },
        }

        # Only add heroImage if we have a valid URL
        if hero_url:
            payload["heroImage"] = {
                "sourceUri": {"uri": hero_url},
                "contentDescription": {
                    "defaultValue": {
                        "language": "en",
                        "value": f"{stamp_count}/{total_stamps} stamps"
                    }
                }
            }

        # Only add logo if we have a valid URL
        logo_url = design.get("logo_url")
        if logo_url:
            payload["logo"] = {
                "sourceUri": {"uri": logo_url},
                "contentDescription": {
                    "defaultValue": {
                        "language": "en",
                        "value": f"{business.get('name', 'Business')} logo"
                    }
                }
            }

        return payload

    def _rgb_to_hex(self, rgb_str: str) -> str:
        """Convert 'rgb(r,g,b)' or '#RRGGBB' to '#RRGGBB'."""
        if not rgb_str:
            return "#8B5A2B"

        rgb_str = rgb_str.strip()

        if rgb_str.startswith("#"):
            # Already hex
            if len(rgb_str) == 4:
                # Short form #RGB -> #RRGGBB
                return f"#{rgb_str[1]*2}{rgb_str[2]*2}{rgb_str[3]*2}"
            return rgb_str

        if rgb_str.startswith("rgb(") and rgb_str.endswith(")"):
            try:
                values = rgb_str[4:-1].split(",")
                r, g, b = [int(v.strip()) for v in values]
                return f"#{r:02x}{g:02x}{b:02x}"
            except (ValueError, IndexError):
                pass

        return "#8B5A2B"  # Default brown

    def _convert_pass_fields_to_text_modules(
        self,
        fields: list[dict],
        prefix: str,
    ) -> list[dict]:
        """
        Convert Apple Wallet PassField format to Google Wallet textModulesData.

        Args:
            fields: List of {key, label, value} dicts from design
            prefix: ID prefix ('sec_', 'aux_', 'back_') for uniqueness

        Returns:
            List of {id, header, body} dicts for textModulesData
        """
        return [
            {
                "id": f"{prefix}{field['key']}",
                "header": field["label"],
                "body": field["value"],
            }
            for field in fields
        ]

    def _build_card_row_template_infos(self, design: dict) -> list[dict]:
        """
        Build cardRowTemplateInfos for the class template.

        This defines which textModulesData fields appear on the card front
        and how they are arranged.

        Layout strategy:
        - Row 1: Stamp count (always present)
        - Row 2: All secondary fields (up to 3 per row)
        - Row 3: All auxiliary fields (up to 3 per row)

        Note: back_fields are NOT included here - they automatically
        appear in the details section since they're not referenced.
        """
        rows = [
            # Row 1: Stamps (always first)
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
            }
        ]

        # Row 2: Secondary fields
        secondary_fields = design.get("secondary_fields", [])
        if secondary_fields:
            secondary_row = self._build_row_from_fields(secondary_fields, "sec_")
            if secondary_row:
                rows.append(secondary_row)

        # Row 3: Auxiliary fields
        auxiliary_fields = design.get("auxiliary_fields", [])
        if auxiliary_fields:
            auxiliary_row = self._build_row_from_fields(auxiliary_fields, "aux_")
            if auxiliary_row:
                rows.append(auxiliary_row)

        return rows

    def _build_row_from_fields(self, fields: list[dict], prefix: str) -> dict | None:
        """
        Build a single card row from a list of fields.

        Google Wallet supports oneItem, twoItems, or threeItems per row.
        """
        if not fields:
            return None

        field_paths = [
            {"fieldPath": f"object.textModulesData['{prefix}{field['key']}']"}
            for field in fields
        ]

        if len(field_paths) == 1:
            return {
                "oneItem": {
                    "item": {
                        "firstValue": {
                            "fields": [field_paths[0]]
                        }
                    }
                }
            }
        elif len(field_paths) == 2:
            return {
                "twoItems": {
                    "startItem": {
                        "firstValue": {
                            "fields": [field_paths[0]]
                        }
                    },
                    "endItem": {
                        "firstValue": {
                            "fields": [field_paths[1]]
                        }
                    }
                }
            }
        else:
            # 3 or more fields - use threeItems (max supported by Google)
            return {
                "threeItems": {
                    "startItem": {
                        "firstValue": {
                            "fields": [field_paths[0]]
                        }
                    },
                    "middleItem": {
                        "firstValue": {
                            "fields": [field_paths[1]]
                        }
                    },
                    "endItem": {
                        "firstValue": {
                            "fields": [field_paths[2]]
                        }
                    }
                }
            }

    def create_or_update_class(
        self,
        business: dict,
        design: dict,
    ) -> str:
        """
        Create or update a GenericClass for a business.

        Returns the class ID.
        """
        class_id = self._get_class_id(business["id"])
        payload = self._build_class_payload(business, design)

        # Try to get existing class
        response = self.http_client.get(
            f"{self.WALLET_API_BASE}/genericClass/{class_id}"
        )

        if response.status_code == 200:
            # Class exists, update it
            response = self.http_client.put(
                f"{self.WALLET_API_BASE}/genericClass/{class_id}",
                json=payload,
            )
        elif response.status_code == 404:
            # Class doesn't exist, create it
            response = self.http_client.post(
                f"{self.WALLET_API_BASE}/genericClass",
                json=payload,
            )
        else:
            response.raise_for_status()

        if response.status_code not in (200, 201):
            response.raise_for_status()

        return class_id

    def create_object(
        self,
        customer: dict,
        business: dict,
        design: dict,
        stamp_count: int = 0,
    ) -> str:
        """
        Create a GenericObject for a customer.

        Returns the object ID.
        """
        object_id = self._get_object_id(customer["id"])
        payload = self._build_object_payload(customer, business, design, stamp_count)

        response = self.http_client.post(
            f"{self.WALLET_API_BASE}/genericObject",
            json=payload,
        )

        # 409 means object already exists - that's okay
        if response.status_code not in (200, 201, 409):
            logger.error(
                f"[Google Wallet] Create failed: {response.status_code} - {response.text}"
            )
            response.raise_for_status()

        return object_id

    def update_object(
        self,
        customer: dict,
        business: dict,
        design: dict,
        stamp_count: int,
    ) -> str:
        """
        Update an existing GenericObject with new stamp count.

        Returns the object ID.
        """
        object_id = self._get_object_id(customer["id"])
        payload = self._build_object_payload(customer, business, design, stamp_count)

        # Use PATCH for partial update
        response = self.http_client.patch(
            f"{self.WALLET_API_BASE}/genericObject/{object_id}",
            json=payload,
        )

        if response.status_code == 404:
            # Object doesn't exist, create it
            return self.create_object(customer, business, design, stamp_count)

        if response.status_code not in (200, 201):
            logger.error(
                f"[Google Wallet] Update failed: {response.status_code} - {response.text}"
            )
            response.raise_for_status()

        return object_id

    def generate_save_url(
        self,
        customer: dict,
        business: dict,
        design: dict,
        stamp_count: int = 0,
    ) -> str:
        """
        Generate a JWT-signed save URL for Google Wallet.

        The URL allows the customer to add the pass to their Google Wallet
        by clicking it. No prior object creation needed - Google will
        create the object from the JWT payload.
        """
        # Build the object payload
        object_payload = self._build_object_payload(
            customer, business, design, stamp_count
        )

        # Also include class info for first-time saves
        class_payload = self._build_class_payload(business, design)

        # Create the JWT claims
        claims = {
            "iss": self.credentials.service_account_email,
            "aud": "google",
            "typ": "savetowallet",
            "iat": int(time.time()),
            "origins": [get_public_base_url()],
            "payload": {
                "genericClasses": [class_payload],
                "genericObjects": [object_payload],
            }
        }

        # Sign with service account private key using Google's JWT library
        token = google_jwt.encode(self.credentials._signer, claims).decode("utf-8")

        return f"{self.SAVE_URL_BASE}/{token}"

    def handle_callback(
        self,
        callback_data: dict,
    ) -> dict:
        """
        Process a Google Wallet callback.

        Google sends callbacks when:
        - A pass is saved to wallet
        - A pass is deleted from wallet
        - A pass is viewed

        Returns:
            Dict with 'action' and 'customer_id' keys
        """
        # Extract callback type and object info
        callback_type = callback_data.get("eventType", "")
        class_id = callback_data.get("classId", "")
        object_id = callback_data.get("objectId", "")

        # Extract customer_id from object_id (format: issuerId.customerId)
        customer_id = None
        if object_id and "." in object_id:
            customer_id = object_id.split(".", 1)[1]

        result = {
            "action": callback_type,
            "customer_id": customer_id,
            "object_id": object_id,
            "class_id": class_id,
        }

        # Handle specific callback types
        if callback_type == "save":
            # User saved pass to wallet
            if customer_id and object_id:
                WalletRegistrationRepository.register_google(
                    customer_id=customer_id,
                    google_object_id=object_id,
                )
            result["registered"] = True

        elif callback_type == "del":
            # User deleted pass from wallet
            if customer_id and object_id:
                WalletRegistrationRepository.unregister_google(
                    customer_id=customer_id,
                    google_object_id=object_id,
                )
            result["unregistered"] = True

        return result

    def send_update_notification(
        self,
        customer_id: str,
    ) -> bool:
        """
        Send update notification for a customer's Google Wallet pass.

        Google Wallet automatically refreshes objects periodically,
        but we can trigger an immediate update by modifying the object.

        Note: Google has a 3 notifications per 24 hours limit.
        """
        # Get registrations for this customer
        registrations = WalletRegistrationRepository.get_google_registrations(customer_id)

        if not registrations:
            return False

        # For each registration, we could trigger a refresh
        # But actually, Google Wallet Generic Passes don't support push updates
        # like Apple Wallet. The pass refreshes when the user opens it.
        #
        # The best we can do is update the object, and Google will reflect
        # the changes when the user views their pass.
        #
        # For real-time updates, we'd need to use Google Wallet's
        # update endpoint which we already do in update_object().

        return True

    def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None


def create_google_wallet_service() -> GoogleWalletService:
    """Factory function to create GoogleWalletService."""
    return GoogleWalletService(
        credentials_path=settings.google_wallet_credentials_path,
        issuer_id=settings.google_wallet_issuer_id,
    )
