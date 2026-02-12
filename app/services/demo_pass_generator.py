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

# Bilingual strings for demo pass (French primary, English translation)
DEMO_STRINGS = {
    "stamps_label": {"fr": "TAMPONS", "en": "STAMPS"},
    "reward_label": {"fr": "RÉCOMPENSE", "en": "REWARD"},
    "reward_completed": {"fr": "🎁 30 jours gratuits !", "en": "🎁 30 days free!"},
    "reward_pending": {"fr": "30 jours d'essai gratuit", "en": "30 days free trial"},
    "org_name": {"fr": "Stampeo Démo", "en": "Stampeo Demo"},
    "description": {"fr": "Carte Démo Interactive Stampeo", "en": "Stampeo Interactive Demo Card"},
    "stamp_change": {
        "fr": "Vous avez gagné un tampon ! Maintenant à %@",
        "en": "You earned a stamp! Now at %@",
    },
    "location_label": {"fr": "📍 Adresse", "en": "📍 Location"},
    "location_value": {"fr": "123 Rue Principale, Paris 75001", "en": "123 Main Street, Paris 75001"},
    "hours_label": {"fr": "🕐 Horaires", "en": "🕐 Opening Hours"},
    "hours_value": {"fr": "Lun-Ven : 8h-19h\nSam-Dim : 9h-17h", "en": "Mon-Fri: 8am-7pm\nSat-Sun: 9am-5pm"},
    "website_label": {"fr": "🌐 Site web", "en": "🌐 Website"},
    "contact_label": {"fr": "📧 Contact", "en": "📧 Contact"},
    "phone_label": {"fr": "📞 Téléphone", "en": "📞 Phone"},
    "social_label": {"fr": "📱 Suivez-nous", "en": "📱 Follow Us"},
    "customize_label": {"fr": "✨ Votre carte, à votre image", "en": "✨ Your Card, Your Way"},
    "customize_value": {
        "fr": "Tous ces champs sont entièrement personnalisables ! Ajoutez votre adresse, vos horaires, votre site web et plus encore.",
        "en": "All these fields are fully customizable! Add your own location, hours, website, and more.",
    },
    "promo_label": {"fr": "Vous avez vu ?", "en": "Did you see that?"},
    "promo_change": {"fr": "Vous avez vu ? %@", "en": "Did you see that? %@"},
    "followup_value": {
        "fr": "Imaginez toucher vos clients comme ça. Prêt à créer votre propre programme de fidélité ? Visitez stampeo.app",
        "en": "Imagine reaching your customers like this. Ready to create your own loyalty program? Visit stampeo.app",
    },
}


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
        """Create demo-specific pass.json with Stampeo branding (French primary)."""
        S = DEMO_STRINGS
        reward_value = S["reward_completed"]["fr"] if stamps >= DEMO_TOTAL_STAMPS else S["reward_pending"]["fr"]

        pass_json = {
            "formatVersion": 1,
            "passTypeIdentifier": self.pass_type_id,
            "teamIdentifier": self.team_id,
            "serialNumber": customer_id,
            "authenticationToken": auth_token,
            "webServiceURL": f"{self.base_url}/demo/wallet",  # Demo-specific endpoint
            "organizationName": S["org_name"]["fr"],
            "description": S["description"]["fr"],
            "logoText": "Stampeo",
            "foregroundColor": DEMO_WHITE,
            "backgroundColor": DEMO_BLACK,
            "labelColor": DEMO_WHITE,
            "storeCard": {
                "headerFields": [
                    {
                        "key": "stamps",
                        "label": S["stamps_label"]["fr"],
                        "value": f"{stamps} / {DEMO_TOTAL_STAMPS}",
                        "changeMessage": S["stamp_change"]["fr"],
                    }
                ],
                "secondaryFields": [
                    {
                        "key": "reward",
                        "label": S["reward_label"]["fr"],
                        "value": reward_value,
                        "changeMessage": "%@",
                    }
                ],
            },
            "barcode": {
                "message": customer_id,
                "format": "PKBarcodeFormatQR",
                "messageEncoding": "iso-8859-1",
            },
            "barcodes": [
                {
                    "message": customer_id,
                    "format": "PKBarcodeFormatQR",
                    "messageEncoding": "iso-8859-1",
                }
            ],
        }

        # Back fields - Stampeo info + demo of customization features
        back_fields = [
            {"key": "location", "label": S["location_label"]["fr"], "value": S["location_value"]["fr"]},
            {"key": "hours", "label": S["hours_label"]["fr"], "value": S["hours_value"]["fr"]},
            {"key": "website", "label": S["website_label"]["fr"], "value": "stampeo.app"},
            {"key": "contact", "label": S["contact_label"]["fr"], "value": "harry.viennot@icloud.com"},
            {"key": "phone", "label": S["phone_label"]["fr"], "value": "06 49 37 04 70"},
            {"key": "social", "label": S["social_label"]["fr"], "value": "@stampeo.app"},
            {"key": "customize", "label": S["customize_label"]["fr"], "value": S["customize_value"]["fr"]},
        ]

        # Add followup message if this is a notification update
        if followup_message:
            back_fields.insert(0, {
                "key": "promo",
                "label": S["promo_label"]["fr"],
                "value": followup_message,
                "changeMessage": S["promo_change"]["fr"],
            })

        pass_json["storeCard"]["backFields"] = back_fields

        return pass_json

    def _create_demo_pass_strings(self) -> bytes:
        """Generate en.lproj/pass.strings mapping French → English (UTF-16).

        Apple Wallet uses this file on English-language devices to replace every
        matching French string from pass.json with its English translation.
        """
        S = DEMO_STRINGS
        lines: list[str] = []

        for key in S:
            fr_val = S[key]["fr"]
            en_val = S[key]["en"]
            if fr_val != en_val:
                fr_escaped = fr_val.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                en_escaped = en_val.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                lines.append(f'"{fr_escaped}" = "{en_escaped}";')

        content = "\n".join(lines) + "\n"
        return content.encode("utf-16")

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

        # Add .lproj translation folders
        # en.lproj: French→English mappings for English-language devices
        files["en.lproj/pass.strings"] = self._create_demo_pass_strings()
        # fr.lproj: empty — makes Apple "stop" here for French devices
        files["fr.lproj/pass.strings"] = b""

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
