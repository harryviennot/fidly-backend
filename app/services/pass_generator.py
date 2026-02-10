import json
import hashlib
import zipfile
import io
from pathlib import Path
from typing import Optional

import httpx

from app.services.strip_generator import StripImageGenerator, StripConfig
from app.services.localization import get_system_string

white = "rgb(255, 255, 255)"

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
        base_url: str,
        signer_cert_pem: bytes,
        signer_key_pem: bytes,
        wwdr_cert_pem: bytes,
        business_name: str = "Coffee Shop",
        strip_config: StripConfig | None = None,
        design: dict | None = None,
        primary_locale: str = "fr",
        translations: dict | None = None,
    ):
        self.team_id = team_id
        self.pass_type_id = pass_type_id
        self.base_url = base_url.rstrip("/")
        self.signer_cert_pem = signer_cert_pem
        self.signer_key_pem = signer_key_pem
        self.wwdr_cert_pem = wwdr_cert_pem
        self.design = design
        self.primary_locale = primary_locale
        self.translations = translations or {}

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
            icon_color=_parse_rgb(design.get("icon_color", white)),
            # Custom strip background as bytes
            strip_background_data=strip_background_data,
            strip_background_opacity=design.get("strip_background_opacity", 40),
        )

    def _create_pass_json(self, customer_id: str, name: str, stamps: int, auth_token: str) -> dict:
        """Create the pass.json content."""
        design = self.design

        # Get values from design or use defaults
        if design:
            org_name = design.get("organization_name", self.business_name)
            description = design.get("description", f"{org_name} Loyalty Card")
            logo_text = design.get("logo_text") or org_name
            foreground_color = design.get("foreground_color", white)
            background_color = design.get("background_color", "rgb(139, 90, 43)")
            label_color = design.get("label_color", white)
            total_stamps = design.get("total_stamps", 10)
            secondary_fields = design.get("secondary_fields", [])
            auxiliary_fields = design.get("auxiliary_fields", [])
            back_fields = design.get("back_fields", [])
        else:
            org_name = self.business_name
            description = f"{self.business_name} Loyalty Card"
            logo_text = self.business_name
            foreground_color = white
            background_color = "rgb(139, 90, 43)"
            label_color = white
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
                        "label": get_system_string("stamps_label", self.primary_locale),
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

    def _create_pass_strings(self, locale: str) -> bytes | None:
        """Generate Apple's pass.strings file for a locale.

        Format: "original_value" = "translated_value"; (UTF-16 encoded).
        Maps primary-language values to their translations so Apple Wallet
        can auto-select based on the device language.
        """
        trans = self.translations.get(locale)
        if not trans:
            return None

        lines: list[str] = []

        # System string: stamps label
        primary_stamps = get_system_string("stamps_label", self.primary_locale)
        translated_stamps = get_system_string("stamps_label", locale)
        if primary_stamps != translated_stamps:
            lines.append(f'"{primary_stamps}" = "{translated_stamps}";')

        # Business content translations
        design = self.design or {}
        field_map = {
            "organization_name": design.get("organization_name", ""),
            "description": design.get("description", ""),
            "logo_text": design.get("logo_text") or design.get("organization_name", ""),
        }
        for field_key, primary_value in field_map.items():
            translated = trans.get(field_key)
            if translated and primary_value and translated != primary_value:
                # Escape quotes in values
                pv = primary_value.replace('"', '\\"')
                tv = translated.replace('"', '\\"')
                lines.append(f'"{pv}" = "{tv}";')

        # Field arrays: secondary_fields, auxiliary_fields, back_fields
        for array_key in ("secondary_fields", "auxiliary_fields", "back_fields"):
            primary_fields = design.get(array_key, [])
            translated_fields = trans.get(array_key, [])
            # Build lookup by key
            trans_by_key = {f["key"]: f for f in translated_fields if isinstance(f, dict) and "key" in f}
            for pf in primary_fields:
                tf = trans_by_key.get(pf.get("key", ""))
                if not tf:
                    continue
                # Translate label
                if tf.get("label") and tf["label"] != pf.get("label", ""):
                    pl = pf["label"].replace('"', '\\"')
                    tl = tf["label"].replace('"', '\\"')
                    lines.append(f'"{pl}" = "{tl}";')
                # Translate value
                if tf.get("value") and tf["value"] != pf.get("value", ""):
                    pv = pf["value"].replace('"', '\\"')
                    tv = tf["value"].replace('"', '\\"')
                    lines.append(f'"{pv}" = "{tv}";')

        if not lines:
            return None

        content = "\n".join(lines) + "\n"
        # Apple requires UTF-16 encoding for pass.strings
        return content.encode("utf-16")

    def _create_manifest(self, files: dict[str, bytes]) -> bytes:
        """Create manifest.json with SHA-1 hashes of all files."""
        manifest = {}
        for filename, content in files.items():
            manifest[filename] = hashlib.sha1(content).hexdigest()
        return json.dumps(manifest).encode("utf-8")

    def _sign_manifest(self, manifest_data: bytes) -> bytes:
        """Create PKCS#7 detached signature using Python cryptography (in-memory)."""
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.serialization import pkcs7

        cert = x509.load_pem_x509_certificate(self.signer_cert_pem)
        key = serialization.load_pem_private_key(self.signer_key_pem, password=None)
        wwdr = x509.load_pem_x509_certificate(self.wwdr_cert_pem)

        return (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(manifest_data)
            .add_signer(cert, key, hashes.SHA256())
            .add_certificate(wwdr)
            .sign(serialization.Encoding.DER, [
                pkcs7.PKCS7Options.DetachedSignature,
                pkcs7.PKCS7Options.Binary,
            ])
        )

    def _get_strip_images(self, stamps: int, design_id: str | None) -> dict[str, bytes]:
        """
        Get strip images using cached/pre-generated strips with fallback to on-the-fly.

        Priority:
        1. Redis cache (fastest - in-memory)
        2. Download from Supabase Storage (pre-generated URLs)
        3. Generate on-the-fly (fallback)
        """
        # Try Redis cache first (if design_id available)
        if design_id:
            try:
                from app.services.strip_cache import get_cached_apple_strips
                cached = get_cached_apple_strips(design_id, stamps)
                if cached:
                    return cached
            except Exception:
                pass  # Cache unavailable, continue to next option

            # Try downloading pre-generated strips from Supabase Storage
            try:
                from app.repositories.strip_image import StripImageRepository
                strip_urls = StripImageRepository.get_apple_urls(design_id, stamps)
                if strip_urls:
                    strips = self._download_strips(strip_urls)
                    if strips:
                        return strips
            except Exception:
                pass  # Pre-generated not available, fall back to on-the-fly

        # Fall back to on-the-fly generation
        return self.strip_generator.generate_all_resolutions(stamps)

    def _download_strips(self, strip_urls: dict[str, str]) -> dict[str, bytes] | None:
        """Download pre-generated strip images from URLs."""
        # Map resolution names to filenames
        resolution_to_filename = {
            "1x": "strip.png",
            "2x": "strip@2x.png",
            "3x": "strip@3x.png",
        }

        result = {}
        for resolution, url in strip_urls.items():
            filename = resolution_to_filename.get(resolution)
            if not filename:
                continue
            data = _download_from_url(url)
            if data is None:
                # If any download fails, return None to trigger fallback
                return None
            result[filename] = data

        # Only return if we got all resolutions
        if len(result) == 3:
            return result
        return None

    def _get_asset_files(self, stamps: int = 0, design_id: str | None = None) -> dict[str, bytes]:
        """Load all pass asset images and get strip images."""
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

        # Get strip images (cached, pre-generated, or on-the-fly)
        strip_images = self._get_strip_images(stamps, design_id)
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

        # Get design_id for cached/pre-generated strip lookup
        design_id = self.design.get("id") if self.design else None

        # Start with asset files (uses cached/pre-generated strips when available)
        files = self._get_asset_files(stamps=stamps, design_id=design_id)

        # Add pass.json
        pass_json = self._create_pass_json(customer_id, name, stamps, auth_token)
        files["pass.json"] = json.dumps(pass_json).encode("utf-8")

        # Add .lproj translation folders for non-primary locales
        has_any_lproj = False
        for locale in self.translations:
            if locale != self.primary_locale:
                pass_strings = self._create_pass_strings(locale)
                if pass_strings:
                    files[f"{locale}.lproj/pass.strings"] = pass_strings
                    has_any_lproj = True

        # Always include a .lproj for the primary locale when other .lproj
        # dirs exist.  Without it Apple Wallet walks the device's preferred-
        # language list (e.g. [fr, en]) and, finding no fr.lproj, falls
        # through to en.lproj — showing English even on a French device.
        # An empty pass.strings is enough to make Apple "stop" at French.
        if has_any_lproj:
            primary_lproj = f"{self.primary_locale}.lproj/pass.strings"
            if primary_lproj not in files:
                files[primary_lproj] = b""

        # Create manifest
        manifest_data = self._create_manifest(files)
        files["manifest.json"] = manifest_data

        # Sign manifest using PKCS7 (in-memory)
        signature = self._sign_manifest(manifest_data)
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
    """Factory function to create PassGenerator from settings (shared certs).

    Used for legacy/demo compatibility where per-business certs are not needed.
    """
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
        base_url=settings.base_url,
        signer_cert_pem=Path(settings.cert_path).read_bytes(),
        signer_key_pem=Path(settings.key_path).read_bytes(),
        wwdr_cert_pem=Path(settings.wwdr_path).read_bytes(),
        business_name=settings.business_name,
        strip_config=strip_config,
        design=design,
    )


def create_pass_generator_for_business(
    business_id: str,
    design: dict | None = None,
    primary_locale: str = "fr",
    translations: dict | None = None,
) -> PassGenerator:
    """Factory that loads per-business certs via CertificateManager."""
    from app.core.config import settings, get_public_base_url
    from app.services.certificate_manager import get_certificate_manager

    cert_manager = get_certificate_manager()
    identifier, signer_cert, signer_key, _ = cert_manager.get_certs_for_business(
        business_id
    )

    wwdr_cert = Path(settings.wwdr_path).read_bytes()

    return PassGenerator(
        team_id=settings.apple_team_id,
        pass_type_id=identifier,
        base_url=get_public_base_url(),
        signer_cert_pem=signer_cert,
        signer_key_pem=signer_key,
        wwdr_cert_pem=wwdr_cert,
        design=design,
        primary_locale=primary_locale,
        translations=translations,
    )


def create_pass_generator_with_active_design(business_id: str | None = None) -> PassGenerator:
    """Factory function that loads the active design from the database."""
    from app.repositories.card_design import CardDesignRepository
    from app.repositories.business import BusinessRepository

    design = None
    primary_locale = "fr"
    translations = None

    if business_id:
        design = CardDesignRepository.get_active(business_id)
        business = BusinessRepository.get_by_id(business_id)
        if business:
            primary_locale = business.get("primary_locale", "fr")
        if design:
            translations = design.get("translations") or {}

    if business_id:
        return create_pass_generator_for_business(
            business_id,
            design=design,
            primary_locale=primary_locale,
            translations=translations,
        )
    return create_pass_generator(design=design)
