"""
Google Wallet pass generator.
Converts card designs to Google Wallet LoyaltyClass/LoyaltyObject format.
"""

import re
from typing import Optional

from app.services.strip_generator import StripImageGenerator, StripConfig


def rgb_to_hex(rgb_str: str) -> str:
    """Convert 'rgb(r,g,b)' to '#RRGGBB'."""
    if not rgb_str:
        return "#1c1c1e"

    rgb_str = rgb_str.strip()

    if rgb_str.startswith("#"):
        return rgb_str

    match = re.match(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', rgb_str)
    if match:
        r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return f"#{r:02x}{g:02x}{b:02x}"

    return "#1c1c1e"  # Default dark color


def _parse_rgb(color_str: str) -> tuple[int, int, int]:
    """Parse 'rgb(r,g,b)' or '#RRGGBB' to RGB tuple."""
    if not color_str:
        return (139, 90, 43)  # Default brown

    color_str = color_str.strip()

    if color_str.startswith("rgb(") and color_str.endswith(")"):
        values = color_str[4:-1].split(",")
        return tuple(int(v.strip()) for v in values)  # type: ignore
    elif color_str.startswith("#"):
        hex_color = color_str[1:]
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore

    return (139, 90, 43)  # Default brown


class GooglePassGenerator:
    """Generates Google Wallet pass data from card designs."""

    def __init__(self, issuer_id: str, base_url: str):
        self.issuer_id = issuer_id
        self.base_url = base_url.rstrip("/")

    def generate_class_id(self, business_id: str) -> str:
        """Generate a unique class ID for a business."""
        # Google requires format: "issuer_id.identifier"
        # Use business UUID as identifier (remove hyphens for cleaner ID)
        clean_id = business_id.replace("-", "")
        return f"{self.issuer_id}.{clean_id}"

    def generate_object_id(self, customer_id: str) -> str:
        """Generate a unique object ID for a customer."""
        clean_id = customer_id.replace("-", "")
        return f"{self.issuer_id}.{clean_id}"

    def design_to_class(self, design: dict, business_id: str, callback_url: Optional[str] = None) -> dict:
        """
        Convert a card design to Google Wallet LoyaltyClass format.

        Args:
            design: Card design from database
            business_id: Business UUID
            callback_url: Optional URL for save/delete callbacks

        Returns:
            LoyaltyClass data ready for Google API
        """
        class_id = self.generate_class_id(business_id)

        class_data = {
            "id": class_id,
            "issuerName": design.get("organization_name", "Loyalty Program"),
            "programName": design.get("description", "Loyalty Card"),
            "hexBackgroundColor": rgb_to_hex(design.get("background_color")),
            "reviewStatus": "UNDER_REVIEW",
        }

        # Add logo if available
        logo_url = design.get("logo_path")
        if logo_url:
            class_data["programLogo"] = {
                "sourceUri": {
                    "uri": logo_url
                },
                "contentDescription": {
                    "defaultValue": {
                        "language": "en",
                        "value": design.get("organization_name", "Logo")
                    }
                }
            }

        # Add hero image (equivalent to Apple's strip image)
        # Generate URL to our dynamic hero image endpoint
        hero_image_url = f"{self.base_url}/google-wallet/hero/{business_id}"
        class_data["heroImage"] = {
            "sourceUri": {
                "uri": hero_image_url
            },
            "contentDescription": {
                "defaultValue": {
                    "language": "en",
                    "value": "Stamp card"
                }
            }
        }

        # Add info module for secondary fields (reward text, etc.)
        secondary_fields = design.get("secondary_fields", [])
        if secondary_fields:
            rows = []
            for field in secondary_fields:
                if field.get("label") and field.get("value"):
                    rows.append({
                        "columns": [{
                            "label": field["label"],
                            "value": field["value"]
                        }]
                    })
            if rows:
                class_data["infoModuleData"] = {"labelValueRows": rows}

        # Add links module for website
        back_fields = design.get("back_fields", [])
        links = []
        for field in back_fields:
            value = field.get("value", "")
            if value.startswith("http://") or value.startswith("https://"):
                links.append({
                    "uri": value,
                    "description": field.get("label", "Link")
                })
        if links:
            class_data["linksModuleData"] = {"uris": links}

        # Add callback URL for save/delete events
        if callback_url:
            class_data["callbackOptions"] = {
                "url": callback_url
            }

        return class_data

    def customer_to_object(
        self,
        customer: dict,
        class_id: str,
        design: dict
    ) -> dict:
        """
        Convert a customer to Google Wallet LoyaltyObject format.

        Args:
            customer: Customer data from database
            class_id: Parent LoyaltyClass ID
            design: Card design for stamp configuration

        Returns:
            LoyaltyObject data ready for Google API or JWT
        """
        customer_id = customer.get("id", "")
        object_id = self.generate_object_id(customer_id)

        total_stamps = design.get("total_stamps", 10)
        stamps = customer.get("stamps", 0)

        object_data = {
            "id": object_id,
            "classId": class_id,
            "state": "ACTIVE",
            "accountId": customer_id,
            "accountName": customer.get("name", "Customer"),
            "loyaltyPoints": {
                "balance": {
                    "int": stamps
                },
                "label": "Stamps",
                "localizedLabel": {
                    "defaultValue": {
                        "language": "en",
                        "value": "Stamps"
                    }
                }
            },
            "barcode": {
                "type": "QR_CODE",
                "value": customer_id,
                "alternateText": customer_id[:8] if customer_id else ""
            },
            "groupingInfo": {
                "groupingId": class_id  # Group all passes from same business
            }
        }

        # Add text modules for stamp progress
        object_data["textModulesData"] = [
            {
                "header": "Progress",
                "body": f"{stamps} / {total_stamps} stamps",
                "id": "progress"
            }
        ]

        # Add congratulations message if reward earned
        if stamps >= total_stamps:
            object_data["messages"] = [
                {
                    "header": "Congratulations!",
                    "body": "You've earned a reward! Show this to redeem.",
                    "id": "reward_ready"
                }
            ]

        return object_data

    def generate_hero_image(self, design: dict, stamps: int = 0) -> bytes:
        """
        Generate a hero image for Google Wallet.

        Google recommends 1032x336 pixels for hero images.
        This reuses the strip generator logic for consistency with Apple.

        Args:
            design: Card design with stamp configuration
            stamps: Current stamp count to show filled

        Returns:
            PNG image bytes
        """
        # Google's hero image dimensions
        # We generate at 3x for quality, similar to Apple's strip@3x
        width = 1032 * 3
        height = 336 * 3

        # Download custom icons if present
        custom_filled_data = None
        custom_empty_data = None
        strip_background_data = None

        if design.get("custom_filled_stamp_path"):
            custom_filled_data = self._download_from_url(design["custom_filled_stamp_path"])

        if design.get("custom_empty_stamp_path"):
            custom_empty_data = self._download_from_url(design["custom_empty_stamp_path"])

        if design.get("strip_background_path"):
            strip_background_data = self._download_from_url(design["strip_background_path"])

        # Build strip config from design
        config = StripConfig(
            width=width,
            height=height,
            stamp_area_height=height,
            background_color=_parse_rgb(design.get("background_color")),
            stamp_filled_color=_parse_rgb(design.get("stamp_filled_color")),
            stamp_empty_color=_parse_rgb(design.get("stamp_empty_color")),
            stamp_border_color=_parse_rgb(design.get("stamp_border_color")),
            total_stamps=design.get("total_stamps", 10),
            stamp_icon=design.get("stamp_icon", "checkmark"),
            reward_icon=design.get("reward_icon", "gift"),
            icon_color=_parse_rgb(design.get("icon_color", "rgb(255,255,255)")),
            custom_filled_icon_data=custom_filled_data,
            custom_empty_icon_data=custom_empty_data,
            strip_background_data=strip_background_data,
        )

        from pathlib import Path
        assets_dir = Path(__file__).parent.parent.parent / "pass_assets"

        generator = StripImageGenerator(config=config, assets_dir=assets_dir)
        return generator.generate(stamps)

    def _download_from_url(self, url: str) -> bytes | None:
        """Download file content from a URL."""
        try:
            import httpx
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return response.content
        except Exception:
            pass
        return None


def create_google_pass_generator() -> GooglePassGenerator:
    """Factory function to create GooglePassGenerator from settings."""
    from app.core.config import settings

    if not settings.google_wallet_issuer_id:
        raise ValueError("Google Wallet issuer ID not configured")

    return GooglePassGenerator(
        issuer_id=settings.google_wallet_issuer_id,
        base_url=settings.base_url
    )
