import json
import hashlib
import zipfile
import os
import io
import subprocess
import tempfile
from pathlib import Path

from app.services.strip_generator import StripImageGenerator, StripConfig


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
    ):
        self.team_id = team_id
        self.pass_type_id = pass_type_id
        self.base_url = base_url.rstrip("/")
        self.business_name = business_name
        self.cert_path = cert_path
        self.key_path = key_path
        self.wwdr_path = wwdr_path
        self.cert_password = cert_password

        # Pass assets directory (relative to project root)
        self.assets_dir = Path(__file__).parent.parent.parent / "pass_assets"

        # Initialize strip image generator for visual stamps
        self.strip_generator = StripImageGenerator(
            config=strip_config or StripConfig(),
            assets_dir=self.assets_dir,
        )

    def _create_pass_json(self, customer_id: str, name: str, stamps: int, auth_token: str) -> dict:
        """Create the pass.json content."""
        return {
            "formatVersion": 1,
            "passTypeIdentifier": self.pass_type_id,
            "teamIdentifier": self.team_id,
            "serialNumber": customer_id,
            "authenticationToken": auth_token,
            "webServiceURL": f"{self.base_url}/wallet",
            "organizationName": self.business_name,
            "description": f"{self.business_name} Loyalty Card",
            "logoText": self.business_name,
            "foregroundColor": "rgb(255, 255, 255)",
            "backgroundColor": "rgb(139, 90, 43)",
            "labelColor": "rgb(255, 255, 255)",
            "storeCard": {
                "headerFields": [
                    {
                        "key": "stamps",
                        "label": "STAMPS",
                        "value": f"{stamps} / 10"
                    }
                ],
                # "primaryFields": [
                #     {
                #         "key": "name",
                #         "label": "MEMBER",
                #         "value": name
                #     }
                # ],
                "secondaryFields": [
                    {
                        "key": "reward",
                        "label": "REWARD",
                        "value": "Free Coffee at 10 stamps!"
                    }
                ],
                # "auxiliaryFields": [
                #     {
                #         "key": "level",
                #         "label": "STATUS",
                #         "value": "Bronze" if stamps < 5 else ("Silver" if stamps < 10 else "Gold")
                #     }
                # ],
                "backFields": [
                    {
                        "key": "terms",
                        "label": "Terms & Conditions",
                        "value": "Earn 1 stamp per purchase. Collect 10 stamps for a free coffee. Stamps expire after 1 year."
                    },
                    {
                        "key": "website",
                        "label": "Website",
                        "value": self.base_url
                    }
                ]
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
        asset_files = [
            "icon.png",
            "icon@2x.png",
            "icon@3x.png",
            "logo.png",
            "logo@2x.png",
        ]

        for filename in asset_files:
            filepath = self.assets_dir / filename
            if filepath.exists():
                with open(filepath, "rb") as f:
                    files[filename] = f.read()

        # Generate dynamic strip images based on stamp count
        strip_images = self.strip_generator.generate_all_resolutions(stamps)
        files.update(strip_images)

        return files

    def generate_pass(self, customer_id: str, name: str, stamps: int, auth_token: str) -> bytes:
        """Generate a complete .pkpass file."""
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


def create_pass_generator() -> PassGenerator:
    """Factory function to create PassGenerator from settings."""
    from app.core.config import settings

    # Build strip config from settings if customization is configured
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
    )
