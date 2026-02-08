"""
Strip Image Service for pre-generating loyalty card stamp strips.

Generates strip images for both Apple and Google Wallet:
- Apple: 1x, 2x, 3x resolutions (375x123 to 1125x369)
- Google: Hero image (1032x336)

Images are uploaded to Supabase Storage and URLs stored in strip_images table.
"""

from typing import Literal
from app.services.strip_generator import StripImageGenerator, StripConfig
from app.services.storage import StorageService, get_storage_service
from app.repositories.strip_image import StripImageRepository


Platform = Literal["apple", "google"]


def _parse_rgb(color_str: str | None) -> tuple[int, int, int]:
    """Parse 'rgb(r,g,b)' or '#RRGGBB' to RGB tuple."""
    if not color_str:
        return (139, 90, 43)  # Default brown

    color_str = color_str.strip()

    if color_str.startswith("rgb(") and color_str.endswith(")"):
        values = color_str[4:-1].split(",")
        return tuple(int(v.strip()) for v in values)  # type: ignore
    elif color_str.startswith("#"):
        hex_color = color_str[1:]
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore

    return (139, 90, 43)  # Default brown


class StripImageService:
    """
    Service for pre-generating and managing strip images.

    Strip images are generated for all stamp counts (0 to total_stamps)
    when a card design is created or updated.
    """

    # Apple Wallet strip dimensions (at 3x scale)
    APPLE_WIDTH = 1125
    APPLE_HEIGHT = 432

    # Google Wallet hero image dimensions
    GOOGLE_HERO_WIDTH = 1032
    GOOGLE_HERO_HEIGHT = 336

    APPLE_RESOLUTIONS = ["1x", "2x", "3x"]

    def __init__(
        self,
        storage: StorageService,
    ):
        self.storage = storage

    def _build_strip_config_from_design(self, design: dict) -> StripConfig:
        """Build StripConfig from a card design dict."""
        # Download custom assets if they exist
        custom_filled_data = None
        custom_empty_data = None
        strip_background_data = None

        if design.get("custom_filled_stamp_path"):
            custom_filled_data = self._download_asset(design["custom_filled_stamp_path"])

        if design.get("custom_empty_stamp_path"):
            custom_empty_data = self._download_asset(design["custom_empty_stamp_path"])

        if design.get("strip_background_path"):
            strip_background_data = self._download_asset(design["strip_background_path"])

        # Get stamp filled color - support both field names
        stamp_filled_color = design.get("stamp_filled_color") or design.get("accent_color")

        return StripConfig(
            background_color=_parse_rgb(design.get("background_color")),
            stamp_filled_color=_parse_rgb(stamp_filled_color),
            stamp_empty_color=_parse_rgb(design.get("stamp_empty_color")),
            stamp_border_color=_parse_rgb(design.get("stamp_border_color")),
            total_stamps=design.get("total_stamps", 10),
            custom_filled_icon_data=custom_filled_data,
            custom_empty_icon_data=custom_empty_data,
            stamp_icon=design.get("stamp_icon", "checkmark"),
            reward_icon=design.get("reward_icon", "gift"),
            icon_color=_parse_rgb(design.get("icon_color", "#ffffff")),
            strip_background_data=strip_background_data,
        )

    def _download_asset(self, url: str) -> bytes | None:
        """Download an asset from URL."""
        import httpx
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return response.content
        except Exception:
            pass
        return None

    def _generate_apple_strips(
        self,
        generator: StripImageGenerator,
        stamp_count: int,
    ) -> dict[str, bytes]:
        """Generate Apple Wallet strip images at all resolutions."""
        return generator.generate_all_resolutions(stamp_count)

    def _generate_google_hero(
        self,
        generator: StripImageGenerator,
        stamp_count: int,
    ) -> bytes:
        """
        Generate Google Wallet hero image.

        Google hero images are 1032x336 pixels.
        Uses dedicated generator method for optimal quality.
        """
        return generator.generate_google_hero(
            stamps=stamp_count,
            width=self.GOOGLE_HERO_WIDTH,
            height=self.GOOGLE_HERO_HEIGHT,
        )

    def _upload_strip(
        self,
        business_id: str,
        design_id: str,
        stamp_count: int,
        platform: Platform,
        resolution: str,
        image_data: bytes,
    ) -> str:
        """Upload a strip image to Supabase Storage and return the URL."""
        # Path: {business_id}/cards/{design_id}/strips/{platform}/strip_{stamp_count}@{resolution}.png
        filename = f"strip_{stamp_count}@{resolution}.png" if resolution != "hero" else f"hero_{stamp_count}.png"
        path = f"{business_id}/cards/{design_id}/strips/{platform}/{filename}"

        return self.storage.upload_file(
            bucket=self.storage.BUSINESSES_BUCKET,
            path=path,
            file_data=image_data,
            content_type="image/png",
        )

    def pregenerate_all_strips(
        self,
        design: dict,
        business_id: str,
    ) -> dict:
        """
        Pre-generate all strip images for a card design.

        This generates strips for all stamp counts (0 to total_stamps)
        for both Apple and Google Wallet.

        Args:
            design: Card design dictionary
            business_id: Business ID for storage path

        Returns:
            Dictionary with:
            - 'urls': {'apple': [...], 'google': [...]} - Storage URLs
            - 'apple_images': {stamp_count: {resolution: bytes}} - For Redis caching
        """
        design_id = design["id"]
        total_stamps = design.get("total_stamps", 10)

        # Build strip config from design
        config = self._build_strip_config_from_design(design)
        generator = StripImageGenerator(config=config)

        urls = {"apple": [], "google": []}
        records = []

        # Store Apple image bytes for caching
        # Format: {stamp_count: {resolution: bytes}}
        apple_images: dict[int, dict[str, bytes]] = {}

        for stamp_count in range(total_stamps + 1):
            apple_images[stamp_count] = {}

            # Generate Apple strips (all resolutions)
            apple_strips = self._generate_apple_strips(generator, stamp_count)
            for res_name, image_data in apple_strips.items():
                # Parse resolution from filename (strip.png -> 1x, strip@2x.png -> 2x, etc.)
                if res_name == "strip.png":
                    resolution = "1x"
                else:
                    resolution = res_name.replace("strip@", "").replace(".png", "")

                # Store image bytes for caching
                apple_images[stamp_count][resolution] = image_data

                url = self._upload_strip(
                    business_id=business_id,
                    design_id=design_id,
                    stamp_count=stamp_count,
                    platform="apple",
                    resolution=resolution,
                    image_data=image_data,
                )
                urls["apple"].append(url)
                records.append({
                    "design_id": design_id,
                    "stamp_count": stamp_count,
                    "platform": "apple",
                    "resolution": resolution,
                    "url": url,
                })

            # Generate Google hero image
            hero_data = self._generate_google_hero(generator, stamp_count)
            hero_url = self._upload_strip(
                business_id=business_id,
                design_id=design_id,
                stamp_count=stamp_count,
                platform="google",
                resolution="hero",
                image_data=hero_data,
            )
            urls["google"].append(hero_url)
            records.append({
                "design_id": design_id,
                "stamp_count": stamp_count,
                "platform": "google",
                "resolution": "hero",
                "url": hero_url,
            })

        # Batch upsert all records to database
        StripImageRepository.upsert_batch(records)

        return {
            "urls": urls,
            "apple_images": apple_images,
        }

    def get_strip_url(
        self,
        design_id: str,
        stamp_count: int,
        platform: Platform,
        resolution: str = "3x",
    ) -> str | None:
        """Get a pre-generated strip URL from the database."""
        return StripImageRepository.get_url(
            design_id=design_id,
            stamp_count=stamp_count,
            platform=platform,
            resolution=resolution,
        )

    def get_apple_strip_urls(
        self,
        design_id: str,
        stamp_count: int,
    ) -> dict[str, str]:
        """Get all Apple strip URLs for a specific stamp count."""
        return StripImageRepository.get_apple_urls(design_id, stamp_count)

    def get_google_hero_url(
        self,
        design_id: str,
        stamp_count: int,
    ) -> str | None:
        """Get Google Wallet hero image URL."""
        return StripImageRepository.get_google_hero_url(design_id, stamp_count)

    def delete_strips_for_design(self, design_id: str) -> int:
        """
        Delete all strip images for a design.
        Used before regenerating strips.

        Returns number of deleted records.
        """
        return StripImageRepository.delete_for_design(design_id)

    def strips_exist_for_design(self, design_id: str) -> bool:
        """Check if strips have been generated for a design."""
        return StripImageRepository.exists_for_design(design_id)


def create_strip_image_service() -> StripImageService:
    """Factory function to create StripImageService."""
    return StripImageService(
        storage=get_storage_service(),
    )
