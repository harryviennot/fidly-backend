"""
Demo pass generator for interactive landing page demo.
Uses fixed Stampeo branding and separate pass type ID.
"""
import json
import hashlib
import zipfile
import os
import io
import subprocess
import tempfile
from pathlib import Path

from app.services.strip_generator import StripImageGenerator, StripConfig


# Stampeo demo branding colors
DEMO_BLACK = "rgb(28, 28, 30)"  # Stampeo black background
DEMO_WHITE = "rgb(255, 255, 255)"
DEMO_GREY = "rgb(156, 163, 175)"  # Label grey
DEMO_ORANGE = "rgb(249, 115, 22)"  # Accent orange
DEMO_TOTAL_STAMPS = 8


class DemoPassGenerator:
    """Pass generator specifically for demo passes with fixed Stampeo branding."""

    def __init__(
        self,
        team_id: str,
        pass_type_id: str,
        cert_path: str,
        key_path: str,
        wwdr_path: str,
        base_url: str,
        cert_password: str | None = None,
    ):
        self.team_id = team_id
        self.pass_type_id = pass_type_id
        self.base_url = base_url.rstrip("/")
        self.cert_path = cert_path
        self.key_path = key_path
        self.wwdr_path = wwdr_path
        self.cert_password = cert_password

        # Pass assets directory
        self.assets_dir = Path(__file__).parent.parent.parent / "pass_assets"

        # Fixed demo strip config (Stampeo black theme)
        strip_config = StripConfig(
            background_color=(28, 28, 30),  # Stampeo black
            stamp_filled_color=(249, 115, 22),  # Orange stamps
            stamp_empty_color=(45, 45, 50),  # Darker grey empty
            stamp_border_color=(156, 163, 175),  # Demo grey border
            total_stamps=DEMO_TOTAL_STAMPS,
            stamp_icon="checkmark",
            reward_icon="gift",
            icon_color=(255, 255, 255),  # White icons
        )

        self.strip_generator = StripImageGenerator(
            config=strip_config,
            assets_dir=self.assets_dir,
        )

    def _create_pass_json(
        self,
        customer_id: str,
        stamps: int,
        auth_token: str,
        followup_message: str | None = None,
    ) -> dict:
        """Create demo-specific pass.json with Stampeo branding."""
        pass_json = {
            "formatVersion": 1,
            "passTypeIdentifier": self.pass_type_id,
            "teamIdentifier": self.team_id,
            "serialNumber": customer_id,
            "authenticationToken": auth_token,
            "webServiceURL": f"{self.base_url}/demo/wallet",  # Demo-specific endpoint
            "organizationName": "Stampeo Demo",
            "description": "Stampeo Interactive Demo Card",
            "logoText": "Stampeo",
            "foregroundColor": DEMO_WHITE,
            "backgroundColor": DEMO_BLACK,
            "labelColor": DEMO_WHITE,
            "storeCard": {
                "headerFields": [
                    {
                        "key": "stamps",
                        "label": "STAMPS",
                        "value": f"{stamps} / {DEMO_TOTAL_STAMPS}",
                        "changeMessage": "You earned a stamp! Now at %@"
                    }
                ],
                "secondaryFields": [
                    {
                        "key": "reward",
                        "label": "REWARD",
                        "value": "🎁 30 days free!" if stamps >= DEMO_TOTAL_STAMPS else "30 days free trial",
                        "changeMessage": "%@"
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

        # Back fields - Stampeo info + demo of customization features
        back_fields = [
            {
                "key": "location",
                "label": "📍 Location",
                "value": "123 Main Street, Paris 75001"
            },
            {
                "key": "hours",
                "label": "🕐 Opening Hours",
                "value": "Mon-Fri: 8am-7pm\nSat-Sun: 9am-5pm"
            },
            {
                "key": "website",
                "label": "🌐 Website",
                "value": "stampeo.app"
            },
            {
                "key": "contact",
                "label": "📧 Contact",
                "value": "harry@stampeo.app"
            },
            {
                "key": "social",
                "label": "📱 Follow Us",
                "value": "@stampeo.app"
            },
            {
                "key": "customize",
                "label": "✨ Your Card, Your Way",
                "value": "All these fields are fully customizable! Add your own location, hours, website, and more."
            },
        ]

        # Add followup message if this is a notification update
        if followup_message:
            back_fields.insert(0, {
                "key": "promo",
                "label": "Did you see that?",
                "value": followup_message,
                "changeMessage": "Did you see that? %@"
            })

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

            with open(manifest_path, "wb") as f:
                f.write(manifest_data)

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

            if self.cert_password:
                cmd.extend(["-passin", f"pass:{self.cert_password}"])

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"OpenSSL signing failed: {result.stderr}")

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

        # Use default logo files for demo
        for filename in ["logo.png", "logo@2x.png"]:
            filepath = self.assets_dir / filename
            if filepath.exists():
                with open(filepath, "rb") as f:
                    files[filename] = f.read()

        # Generate dynamic strip images based on stamp count
        strip_images = self.strip_generator.generate_all_resolutions(stamps)
        files.update(strip_images)

        return files

    def generate_demo_pass(
        self,
        customer_id: str,
        stamps: int,
        auth_token: str,
        followup_message: str | None = None,
    ) -> bytes:
        """Generate a complete .pkpass file for demo."""
        # Start with asset files (includes dynamic strip based on stamps)
        files = self._get_asset_files(stamps=stamps)

        # Add pass.json
        pass_json = self._create_pass_json(
            customer_id, stamps, auth_token, followup_message
        )
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


def create_demo_pass_generator() -> DemoPassGenerator:
    """Factory function for demo pass generator."""
    from app.core.config import settings

    return DemoPassGenerator(
        team_id=settings.apple_team_id,
        pass_type_id=settings.demo_pass_type_id,
        cert_path=settings.demo_cert_path,
        key_path=settings.demo_key_path,
        wwdr_path=settings.demo_wwdr_path,
        base_url=settings.base_url,
        cert_password=settings.demo_cert_password,
    )
