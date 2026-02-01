import json
import hashlib
import zipfile
import os
import io
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import httpx

from app.services.strip_generator import StripImageGenerator, StripConfig


def _download_from_url(url: str) -> bytes | None:
    """Download file content from a URL."""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            if response.status_code == 200:
                return response.content
    except Exception:
        pass
    return None


class PassGenerator:
    def __init__(
        self,
        team_id: str,
        pass_type_id: str,
        cert_path: str,
        key_path: str,
        wwdr_path: str,
        base_url: str,
        business_name: str = "Coffee Shop",
        cert_password: str | None = None,
        strip_config: StripConfig | None = None,
        design: dict | None = None,
    ):
        self.team_id = team_id
        self.pass_type_id = pass_type_id
        self.base_url = base_url.rstrip("/")
        self.cert_path = cert_path
        self.key_path = key_path
        self.wwdr_path = wwdr_path
        self.cert_password = cert_password
        self.design = design

        # Use design values if available, otherwise fall back to defaults/params
        if design:
            self.business_name = design.get("organization_name", business_name)
        else:
            self.business_name = business_name

        # Pass assets directory (relative to project root)
        self.assets_dir = Path(__file__).parent.parent.parent / "pass_assets"

        # Build strip config from design if available
        if design:
            strip_config = self._build_strip_config_from_design(design)

        # Initialize strip image generator for visual stamps
        self.strip_generator = StripImageGenerator(
            config=strip_config or StripConfig(),
            assets_dir=self.assets_dir,
        )

    def _build_strip_config_from_design(self, design: dict) -> StripConfig:
        """Build StripConfig from a design dictionary."""
        # Download custom stamp icons from Supabase Storage URLs if they exist
        custom_filled_data = None
        custom_empty_data = None
        strip_background_data = None

        if design.get("custom_filled_stamp_path"):
            custom_filled_data = _download_from_url(design["custom_filled_stamp_path"])

        if design.get("custom_empty_stamp_path"):
            custom_empty_data = _download_from_url(design["custom_empty_stamp_path"])

        if design.get("strip_background_path"):
            strip_background_data = _download_from_url(design["strip_background_path"])

        # Get stamp filled color - support both stamp_filled_color and accent_color (from onboarding)
        stamp_filled_color = design.get("stamp_filled_color") or design.get("accent_color")

        return StripConfig(
            background_color=_parse_rgb(design.get("background_color")),
            stamp_filled_color=_parse_rgb(stamp_filled_color),
            stamp_empty_color=_parse_rgb(design.get("stamp_empty_color")),
            stamp_border_color=_parse_rgb(design.get("stamp_border_color")),
            total_stamps=design.get("total_stamps", 10),
            # Custom icons as bytes (downloaded from Supabase Storage)
            custom_filled_icon_data=custom_filled_data,
            custom_empty_icon_data=custom_empty_data,
            # New predefined icon configuration
            stamp_icon=design.get("stamp_icon", "checkmark"),
            reward_icon=design.get("reward_icon", "gift"),
            icon_color=_parse_rgb(design.get("icon_color", "#ffffff")),
            # Custom strip background as bytes
            strip_background_data=strip_background_data,
        )

    def _create_pass_json(self, customer_id: str, name: str, stamps: int, auth_token: str) -> dict:
        """Create the pass.json content."""
        design = self.design

        # Get values from design or use defaults
        if design:
            org_name = design.get("organization_name", self.business_name)
            description = design.get("description", f"{org_name} Loyalty Card")
            logo_text = design.get("logo_text") or org_name
            foreground_color = design.get("foreground_color", "rgb(255, 255, 255)")
            background_color = design.get("background_color", "rgb(139, 90, 43)")
            label_color = design.get("label_color", "rgb(255, 255, 255)")
            total_stamps = design.get("total_stamps", 10)
            secondary_fields = design.get("secondary_fields", [])
            auxiliary_fields = design.get("auxiliary_fields", [])
            back_fields = design.get("back_fields", [])
        else:
            org_name = self.business_name
            description = f"{self.business_name} Loyalty Card"
            logo_text = self.business_name
            foreground_color = "rgb(255, 255, 255)"
            background_color = "rgb(139, 90, 43)"
            label_color = "rgb(255, 255, 255)"
            total_stamps = 10
            secondary_fields = [
                {"key": "reward", "label": "REWARD", "value": "Free Coffee at 10 stamps!"}
            ]
            auxiliary_fields = []
            back_fields = [
                {"key": "terms", "label": "Terms & Conditions", "value": "Earn 1 stamp per purchase. Collect 10 stamps for a free coffee. Stamps expire after 1 year."},
                {"key": "website", "label": "Website", "value": self.base_url}
            ]

        pass_json = {
            "formatVersion": 1,
            "passTypeIdentifier": self.pass_type_id,
            "teamIdentifier": self.team_id,
            "serialNumber": customer_id,
            "authenticationToken": auth_token,
            "webServiceURL": f"{self.base_url}/wallet",
            "organizationName": org_name,
            "description": description,
            "logoText": logo_text,
            "foregroundColor": foreground_color,
            "backgroundColor": background_color,
            "labelColor": label_color,
            "storeCard": {
                "headerFields": [
                    {
                        "key": "stamps",
                        "label": "STAMPS",
                        "value": f"{stamps} / {total_stamps}"
                    }
                ],
            },
            "barcode": {
                "message": customer_id,
                "format": "PKBarcodeFormatQR",
                "messageEncoding": "iso-8859-1"
            },
            "barcodes": [
                {
                    "message": customer_id,
                    "format": "PKBarcodeFormatQR",
                    "messageEncoding": "iso-8859-1"
                }
            ]
        }

        # Add secondary fields if any
        if secondary_fields:
            pass_json["storeCard"]["secondaryFields"] = secondary_fields

        # Add auxiliary fields if any
        if auxiliary_fields:
            pass_json["storeCard"]["auxiliaryFields"] = auxiliary_fields

        # Add back fields if any
        if back_fields:
            pass_json["storeCard"]["backFields"] = back_fields

        return pass_json

    def _create_manifest(self, files: dict[str, bytes]) -> bytes:
        """Create manifest.json with SHA-1 hashes of all files."""
        manifest = {}
        for filename, content in files.items():
            manifest[filename] = hashlib.sha1(content).hexdigest()
        return json.dumps(manifest).encode("utf-8")

    def _sign_manifest_openssl(self, manifest_data: bytes) -> bytes:
        """Create PKCS#7 detached signature using OpenSSL CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, "manifest.json")
            signature_path = os.path.join(tmpdir, "signature")

            # Write manifest to temp file
            with open(manifest_path, "wb") as f:
                f.write(manifest_data)

            # Build openssl command
            cmd = [
                "openssl", "smime", "-sign",
                "-signer", self.cert_path,
                "-inkey", self.key_path,
                "-certfile", self.wwdr_path,
                "-in", manifest_path,
                "-out", signature_path,
                "-outform", "DER",
                "-binary",
            ]

            # Add password if provided
            if self.cert_password:
                cmd.extend(["-passin", f"pass:{self.cert_password}"])

            # Run openssl
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"OpenSSL signing failed: {result.stderr}")

            # Read signature
            with open(signature_path, "rb") as f:
                return f.read()

    def _get_asset_files(self, stamps: int = 0) -> dict[str, bytes]:
        """Load all pass asset images and generate dynamic strip."""
        files = {}

        # Load icon files from default assets
        icon_files = ["icon.png", "icon@2x.png", "icon@3x.png"]
        for filename in icon_files:
            filepath = self.assets_dir / filename
            if filepath.exists():
                with open(filepath, "rb") as f:
                    files[filename] = f.read()

        # Load logo - check for custom design logo URL first (from Supabase Storage)
        logo_loaded = False
        if self.design and self.design.get("logo_path"):
            logo_data = _download_from_url(self.design["logo_path"])
            if logo_data:
                files["logo.png"] = logo_data
                files["logo@2x.png"] = logo_data
                logo_loaded = True

        # Fall back to default logo files
        if not logo_loaded:
            for filename in ["logo.png", "logo@2x.png"]:
                filepath = self.assets_dir / filename
                if filepath.exists():
                    with open(filepath, "rb") as f:
                        files[filename] = f.read()

        # Generate dynamic strip images based on stamp count
        strip_images = self.strip_generator.generate_all_resolutions(stamps)
        files.update(strip_images)

        return files

    def generate_pass(
        self,
        customer_id: str,
        name: str,
        stamps: int,
        auth_token: str,
        business_id: str | None = None,
    ) -> bytes:
        """Generate a complete .pkpass file."""
        # If business_id is provided and we don't have a design, load it
        if business_id and not self.design:
            from app.repositories.card_design import CardDesignRepository
            design = CardDesignRepository.get_active(business_id)
            if design:
                self.design = design
                self.business_name = design.get("organization_name", self.business_name)
                self.strip_generator = StripImageGenerator(
                    config=self._build_strip_config_from_design(design),
                    assets_dir=self.assets_dir,
                )

        # Start with asset files (includes dynamic strip based on stamps)
        files = self._get_asset_files(stamps=stamps)

        # Add pass.json
        pass_json = self._create_pass_json(customer_id, name, stamps, auth_token)
        files["pass.json"] = json.dumps(pass_json).encode("utf-8")

        # Create manifest
        manifest_data = self._create_manifest(files)
        files["manifest.json"] = manifest_data

        # Sign manifest using OpenSSL
        signature = self._sign_manifest_openssl(manifest_data)
        files["signature"] = signature

        # Create ZIP file
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename, content in files.items():
                zf.writestr(filename, content)

        return buffer.getvalue()


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


def create_pass_generator(design: dict | None = None) -> PassGenerator:
    """Factory function to create PassGenerator from settings and optional design."""
    from app.core.config import settings

    # If no design provided, use settings-based strip config as fallback
    strip_config = None
    if not design:
        strip_config = StripConfig(
            background_color=_parse_rgb(settings.strip_background_color),
            stamp_filled_color=_parse_rgb(settings.strip_stamp_filled_color),
            stamp_empty_color=_parse_rgb(settings.strip_stamp_empty_color),
            stamp_border_color=_parse_rgb(settings.strip_stamp_border_color),
            custom_filled_icon=settings.strip_custom_filled_icon,
            custom_empty_icon=settings.strip_custom_empty_icon,
        )

    return PassGenerator(
        team_id=settings.apple_team_id,
        pass_type_id=settings.apple_pass_type_id,
        cert_path=settings.cert_path,
        key_path=settings.key_path,
        wwdr_path=settings.wwdr_path,
        base_url=settings.base_url,
        business_name=settings.business_name,
        cert_password=settings.cert_password,
        strip_config=strip_config,
        design=design,
    )


def create_pass_generator_with_active_design(business_id: str | None = None) -> PassGenerator:
    """Factory function that loads the active design from the database."""
    from app.repositories.card_design import CardDesignRepository

    design = None
    if business_id:
        design = CardDesignRepository.get_active(business_id)
    return create_pass_generator(design=design)
