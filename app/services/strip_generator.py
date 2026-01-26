"""
Strip image generator for Apple Wallet loyalty pass.
Generates dynamic punch card visuals based on stamp count.
"""

from dataclasses import dataclass
from typing import Optional, Union
from pathlib import Path
import io

from PIL import Image, ImageDraw, ImageFont


@dataclass
class StripConfig:
    """Configuration for strip image generation."""

    # Dimensions (strip.png requirements for storeCard)
    # @3x: 1125 x 432, @2x: 750 x 288, @1x: 375 x 144
    width: int = 1125
    height: int = 432

    # Colors (RGB tuples)
    background_color: tuple[int, int, int] = (139, 90, 43)  # Coffee brown
    background_gradient_end: Optional[tuple[int, int, int]] = None

    # Stamp appearance
    stamp_filled_color: tuple[int, int, int] = (255, 215, 0)  # Gold
    stamp_empty_color: tuple[int, int, int] = (80, 50, 20)  # Dark brown
    stamp_border_color: tuple[int, int, int] = (255, 255, 255)  # White
    stamp_border_width: int = 4

    # Layout
    total_stamps: int = 10  # Must be multiple of 2, max 10
    # Note: stamp_radius is now calculated dynamically based on total_stamps
    # These are kept for backwards compatibility but may be overridden
    stamp_radius: int = 80
    stamp_spacing: int = 55
    stamps_per_row: int = 10  # Single row - all stamps in one line

    # Text
    show_progress_text: bool = True
    text_color: tuple[int, int, int] = (255, 255, 255)
    font_size: int = 32

    # Custom stamp icons (optional filenames in stamps/ directory)
    custom_filled_icon: Optional[str] = None
    custom_empty_icon: Optional[str] = None


class StripImageGenerator:
    """Generates strip.png images for Apple Wallet passes."""

    def __init__(
        self,
        config: Optional[StripConfig] = None,
        assets_dir: Optional[Path] = None,
    ):
        self.config = config or StripConfig()
        self.assets_dir = assets_dir
        self._custom_filled: Optional[Image.Image] = None
        self._custom_empty: Optional[Image.Image] = None
        self._load_custom_icons()

    def _load_custom_icons(self) -> None:
        """Load custom stamp icons if configured."""
        if not self.assets_dir:
            return

        stamps_dir = self.assets_dir / "stamps"
        if not stamps_dir.exists():
            return

        if self.config.custom_filled_icon:
            icon_path = stamps_dir / self.config.custom_filled_icon
            if icon_path.exists():
                self._custom_filled = Image.open(icon_path).convert("RGBA")

        if self.config.custom_empty_icon:
            icon_path = stamps_dir / self.config.custom_empty_icon
            if icon_path.exists():
                self._custom_empty = Image.open(icon_path).convert("RGBA")

    def _create_background(self, width: int, height: int) -> Image.Image:
        """Create the background with optional gradient."""
        img = Image.new("RGB", (width, height), self.config.background_color)

        if self.config.background_gradient_end:
            draw = ImageDraw.Draw(img)
            r1, g1, b1 = self.config.background_color
            r2, g2, b2 = self.config.background_gradient_end

            for y in range(height):
                ratio = y / height
                r = int(r1 + (r2 - r1) * ratio)
                g = int(g1 + (g2 - g1) * ratio)
                b = int(b1 + (b2 - b1) * ratio)
                draw.line([(0, y), (width, y)], fill=(r, g, b))

        return img

    def _draw_stamp_circle(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        radius: int,
        filled: bool,
        border_width: int,
    ) -> None:
        """Draw a single stamp circle."""
        fill_color = (
            self.config.stamp_filled_color if filled else self.config.stamp_empty_color
        )

        # Draw the circle
        draw.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            fill=fill_color,
            outline=self.config.stamp_border_color,
            width=border_width,
        )

        # If filled, add an inner accent (checkmark-like dot)
        if filled:
            inner_radius = int(radius * 0.35)
            accent_color = (50, 30, 10)  # Dark accent for contrast
            draw.ellipse(
                [x - inner_radius, y - inner_radius, x + inner_radius, y + inner_radius],
                fill=accent_color,
            )

    def _paste_custom_icon(
        self,
        img: Image.Image,
        x: int,
        y: int,
        radius: int,
        filled: bool,
    ) -> bool:
        """Paste a custom stamp icon. Returns True if successful."""
        icon = self._custom_filled if filled else self._custom_empty
        if icon is None:
            return False

        # Resize icon to fit stamp size
        size = radius * 2
        resized = icon.resize((size, size), Image.Resampling.LANCZOS)

        # Center the icon at (x, y)
        paste_x = x - radius
        paste_y = y - radius

        # Convert main image to RGBA for pasting with transparency
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        img.paste(resized, (paste_x, paste_y), resized)
        return True

    def _calculate_dynamic_stamp_size(self, width: int) -> tuple[int, int]:
        """Calculate stamp radius and spacing based on total stamps and width.

        Returns (radius, spacing) tuple.
        """
        total = self.config.total_stamps

        # Leave padding on sides (about 5% of width on each side)
        padding = int(width * 0.05)
        available_width = width - (2 * padding)

        # Spacing is about 15% of diameter
        # Formula: total * diameter + (total - 1) * spacing = available_width
        # With spacing = 0.15 * diameter:
        # total * diameter + (total - 1) * 0.15 * diameter = available_width
        # diameter * (total + 0.15 * (total - 1)) = available_width
        # diameter = available_width / (total + 0.15 * (total - 1))

        spacing_ratio = 0.15
        diameter = available_width / (total + spacing_ratio * (total - 1))
        radius = int(diameter / 2)
        spacing = int(diameter * spacing_ratio)

        return radius, spacing

    def _calculate_stamp_positions(
        self,
        width: int,
        height: int,
        radius: int,
        spacing: int,
    ) -> list[tuple[int, int]]:
        """Calculate (x, y) positions for all stamps in a single row."""
        positions = []
        total = self.config.total_stamps

        # Single row layout
        stamp_diameter = radius * 2
        row_width = (total * stamp_diameter) + ((total - 1) * spacing)
        start_x = (width - row_width) // 2 + radius

        # Center vertically
        center_y = height // 2

        for i in range(total):
            x = start_x + i * (stamp_diameter + spacing)
            y = center_y
            positions.append((x, y))

        return positions

    def _get_font(self, size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
        """Get a font, falling back to default if needed."""
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSText.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
        ]

        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, size)
            except (OSError, IOError):
                continue

        return ImageFont.load_default()

    def _generate_at_scale(self, stamps: int, scale: int) -> bytes:
        """Generate strip image at a specific scale (1, 2, or 3)."""
        # Scale dimensions
        width = (self.config.width * scale) // 3
        height = (self.config.height * scale) // 3

        # Calculate dynamic stamp size based on total stamps
        radius, spacing = self._calculate_dynamic_stamp_size(width)

        border_width = max(1, max(2, radius // 20))  # Border proportional to radius
        font_size = (self.config.font_size * scale) // 3

        # Clamp stamps to valid range
        stamps = max(0, min(stamps, self.config.total_stamps))

        # Create background
        img = self._create_background(width, height)
        draw = ImageDraw.Draw(img)

        # Calculate positions
        positions = self._calculate_stamp_positions(width, height, radius, spacing)

        # Draw stamps
        for i, (x, y) in enumerate(positions):
            filled = i < stamps

            # Try custom icons first
            if filled and self._custom_filled:
                self._paste_custom_icon(img, x, y, radius, True)
            elif not filled and self._custom_empty:
                self._paste_custom_icon(img, x, y, radius, False)
            else:
                self._draw_stamp_circle(draw, x, y, radius, filled, border_width)

        # # Add progress text
        # if self.config.show_progress_text:
        #     if stamps >= self.config.total_stamps:
        #         text = "REWARD READY!"
        #     else:
        #         text = f"{stamps}/{self.config.total_stamps} stamps"

        #     font = self._get_font(font_size)
        #     bbox = draw.textbbox((0, 0), text, font=font)
        #     text_width = bbox[2] - bbox[0]
        #     text_x = (width - text_width) // 2
        #     text_y = height - font_size - 20

        #     draw.text((text_x, text_y), text, fill=self.config.text_color, font=font)

        # Convert to PNG bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    def generate(self, stamps: int) -> bytes:
        """Generate strip image at @3x resolution."""
        return self._generate_at_scale(stamps, scale=3)

    def generate_all_resolutions(self, stamps: int) -> dict[str, bytes]:
        """
        Generate strip images for all required resolutions.

        Returns dict with keys: 'strip.png', 'strip@2x.png', 'strip@3x.png'
        """
        return {
            "strip.png": self._generate_at_scale(stamps, scale=1),
            "strip@2x.png": self._generate_at_scale(stamps, scale=2),
            "strip@3x.png": self._generate_at_scale(stamps, scale=3),
        }
