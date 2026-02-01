"""
Strip image generator for Apple Wallet loyalty pass.
Generates dynamic punch card visuals based on stamp count.
"""

from dataclasses import dataclass
from typing import Optional, Union, List
from pathlib import Path
import io
import re

from PIL import Image, ImageDraw, ImageFont

# Optional import for SVG rendering
try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except ImportError:
    CAIROSVG_AVAILABLE = False


# Valid predefined icon names
ICON_NAMES = {
    "checkmark", "coffee", "star", "heart", "gift", "thumbsup",
    "sparkle", "trophy", "crown", "lightning", "fire", "sun",
    "leaf", "flower", "diamond", "smiley", "music", "paw",
    "scissors", "food", "shopping", "percent"
}


@dataclass
class CirclePosition:
    """Represents a circle with its center position and radius."""
    center_x: float
    center_y: float
    radius: float
    row: int
    index: int


@dataclass
class CircleLayout:
    """Complete layout information for circle placement."""
    circles: List[CirclePosition]
    diameter: float
    radius: float
    rows: int
    distribution: List[int]
    vertical_padding: float
    horizontal_paddings: List[float]
    canvas_width: int
    canvas_height: int


@dataclass
class StripConfig:
    """Configuration for strip image generation."""

    # Dimensions (strip.png requirements for storeCard)
    # @3x: 1125 x 369, @2x: 750 x 246, @1x: 375 x 123
    # Note: Using 369 for stamp area (432 - 63 for top safe area)
    width: int = 1125
    height: int = 432
    stamp_area_height: int = 369  # Actual area for stamps

    # Colors (RGB tuples)
    background_color: tuple[int, int, int] = (139, 90, 43)  # Coffee brown
    background_gradient_end: Optional[tuple[int, int, int]] = None

    # Stamp appearance
    stamp_filled_color: tuple[int, int, int] = (255, 215, 0)  # Gold
    stamp_empty_color: tuple[int, int, int] = (80, 50, 20)  # Dark brown
    stamp_border_color: tuple[int, int, int] = (255, 255, 255)  # White
    stamp_border_width: int = 4

    # Layout
    total_stamps: int = 10  # 1-24 stamps supported
    min_padding: int = 16  # Minimum padding between stamps and edges

    # Text
    show_progress_text: bool = True
    text_color: tuple[int, int, int] = (255, 255, 255)
    font_size: int = 32

    # Custom stamp icons as file paths (legacy, for local files)
    custom_filled_icon: Optional[str] = None
    custom_empty_icon: Optional[str] = None

    # Custom stamp icons as bytes data (for Supabase Storage downloads)
    custom_filled_icon_data: Optional[bytes] = None
    custom_empty_icon_data: Optional[bytes] = None

    # Predefined icon configuration
    stamp_icon: str = "checkmark"  # Icon for regular stamps
    reward_icon: str = "gift"  # Icon for the last (reward) stamp
    icon_color: tuple[int, int, int] = (255, 255, 255)  # Color of icon inside stamps

    # Custom strip background (path for legacy, bytes for Supabase Storage)
    strip_background_path: Optional[str] = None
    strip_background_data: Optional[bytes] = None


def get_row_distribution(count: int) -> List[int]:
    """
    Get the row distribution for a given circle count.
    
    - 1-6: Single row
    - 7-16: Two rows (split evenly, larger on top)
    - 17-24: Three rows (balanced distribution)
    
    Args:
        count: Number of circles (1-24)
    
    Returns:
        List of circle counts per row (top to bottom)
    """
    if count <= 0:
        return [0]
    
    if count <= 6:
        return [count]
    
    elif count <= 16:
        # Two rows - split as evenly as possible, larger on top
        top_row = (count + 1) // 2  # Ceiling division
        bottom_row = count - top_row
        return [top_row, bottom_row]
    
    else:
        # Three rows (17-24)
        distribution_map = {
            17: [6, 6, 5],
            18: [6, 6, 6],
            19: [7, 7, 5],
            20: [7, 7, 6],
            21: [7, 7, 7],
            22: [8, 8, 6],
            23: [8, 8, 7],
            24: [8, 8, 8],
        }
        return distribution_map.get(count, [8, 8, 8])


def calculate_circle_layout(
    count: int,
    canvas_width: int = 1125,
    canvas_height: int = 369,
    min_padding: int = 16
) -> CircleLayout:
    """
    Calculate circle positions for a given count on the canvas.
    
    Uses equal padding: padding between edge and first circle equals
    padding between circles (per row for horizontal, uniform for vertical).
    
    Args:
        count: Number of circles (1-24)
        canvas_width: Width of canvas in pixels
        canvas_height: Height of canvas in pixels
        min_padding: Minimum padding in pixels (Apple Wallet style: 24)
    
    Returns:
        CircleLayout object with all positioning information
    """
    if count <= 0:
        return CircleLayout(
            circles=[],
            diameter=0,
            radius=0,
            rows=0,
            distribution=[],
            vertical_padding=0,
            horizontal_paddings=[],
            canvas_width=canvas_width,
            canvas_height=canvas_height
        )
    
    # Clamp to valid range
    count = min(count, 24)
    
    # Determine number of rows and distribution
    distribution = get_row_distribution(count)
    rows = len(distribution)
    
    # Find the maximum circles in any row to determine circle size
    max_in_row = max(distribution)
    
    # Calculate circle diameter based on available space
    # Width constraint: (max_in_row * diameter) + ((max_in_row + 1) * padding) <= canvas_width
    # Height constraint: (rows * diameter) + ((rows + 1) * padding) <= canvas_height
    max_diameter_by_width = (canvas_width - (max_in_row + 1) * min_padding) / max_in_row
    max_diameter_by_height = (canvas_height - (rows + 1) * min_padding) / rows
    
    # Use the smaller to ensure both constraints are met
    diameter = min(max_diameter_by_width, max_diameter_by_height)
    radius = diameter / 2
    
    # Calculate vertical padding (same between all rows and edges)
    total_vertical_space = canvas_height - (rows * diameter)
    vertical_padding = total_vertical_space / (rows + 1)
    
    # Calculate positions for each circle
    circles = []
    horizontal_paddings = []
    circle_index = 0
    
    for row_index, circles_in_row in enumerate(distribution):
        if circles_in_row == 0:
            continue
            
        # Horizontal padding for this row (same between all circles and edges)
        total_horizontal_space = canvas_width - (circles_in_row * diameter)
        horizontal_padding = total_horizontal_space / (circles_in_row + 1)
        horizontal_paddings.append(horizontal_padding)
        
        # Y position for this row (center of circle)
        y = vertical_padding * (row_index + 1) + diameter * row_index + radius
        
        for i in range(circles_in_row):
            # X position (center of circle)
            x = horizontal_padding * (i + 1) + diameter * i + radius
            circles.append(CirclePosition(
                center_x=x,
                center_y=y,
                radius=radius,
                row=row_index,
                index=circle_index
            ))
            circle_index += 1
    
    return CircleLayout(
        circles=circles,
        diameter=diameter,
        radius=radius,
        rows=rows,
        distribution=distribution,
        vertical_padding=vertical_padding,
        horizontal_paddings=horizontal_paddings,
        canvas_width=canvas_width,
        canvas_height=canvas_height
    )


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
        self._icon_cache: dict[str, Image.Image] = {}
        self._load_custom_icons()

    def _load_custom_icons(self) -> None:
        """Load custom stamp icons if configured (from bytes or file paths)."""
        # First try loading from bytes data (Supabase Storage)
        if self.config.custom_filled_icon_data:
            try:
                self._custom_filled = Image.open(
                    io.BytesIO(self.config.custom_filled_icon_data)
                ).convert("RGBA")
            except Exception:
                pass

        if self.config.custom_empty_icon_data:
            try:
                self._custom_empty = Image.open(
                    io.BytesIO(self.config.custom_empty_icon_data)
                ).convert("RGBA")
            except Exception:
                pass

        # Fall back to file paths (legacy support)
        if not self._custom_filled and self.config.custom_filled_icon and self.assets_dir:
            stamps_dir = self.assets_dir / "stamps"
            if stamps_dir.exists():
                icon_path = stamps_dir / self.config.custom_filled_icon
                if icon_path.exists():
                    self._custom_filled = Image.open(icon_path).convert("RGBA")

        if not self._custom_empty and self.config.custom_empty_icon and self.assets_dir:
            stamps_dir = self.assets_dir / "stamps"
            if stamps_dir.exists():
                icon_path = stamps_dir / self.config.custom_empty_icon
                if icon_path.exists():
                    self._custom_empty = Image.open(icon_path).convert("RGBA")

    def _get_icons_dir(self) -> Path:
        """Get path to bundled icons directory."""
        return Path(__file__).parent.parent.parent / "assets" / "icons"

    def _load_icon(
        self,
        icon_name: str,
        color: tuple[int, int, int],
        size: int
    ) -> Optional[Image.Image]:
        """Load SVG icon and render with custom color at specified size."""
        if not CAIROSVG_AVAILABLE:
            return None

        if icon_name not in ICON_NAMES:
            return None

        # Create cache key
        cache_key = f"{icon_name}_{color}_{size}"
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        svg_path = self._get_icons_dir() / f"{icon_name}.svg"
        if not svg_path.exists():
            return None

        try:
            # Read SVG content
            svg_content = svg_path.read_text()

            # Replace fill color in SVG (Phosphor uses currentColor or #000)
            hex_color = f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"

            # Replace fill="currentColor" and fill="#000000" etc.
            svg_content = svg_content.replace('fill="currentColor"', f'fill="{hex_color}"')
            svg_content = re.sub(r'fill="#[0-9a-fA-F]{3,6}"', f'fill="{hex_color}"', svg_content)

            # Also handle style-based fills
            svg_content = re.sub(r'fill:[^;"}]*', f'fill:{hex_color}', svg_content)

            # Render SVG to PNG bytes
            png_bytes = cairosvg.svg2png(
                bytestring=svg_content.encode(),
                output_width=size,
                output_height=size
            )

            # Convert to PIL Image
            icon_img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            self._icon_cache[cache_key] = icon_img
            return icon_img

        except Exception:
            # Fall back gracefully if SVG rendering fails
            return None

    def _create_background(self, width: int, height: int) -> Image.Image:
        """Create the background with optional custom image or gradient."""
        # Try custom background from bytes data first (Supabase Storage)
        if self.config.strip_background_data:
            try:
                bg_img = Image.open(io.BytesIO(self.config.strip_background_data)).convert("RGB")
                bg_img = self._resize_cover(bg_img, width, height)
                return bg_img
            except Exception:
                pass  # Fall back to other options

        # Try custom background image from file path (legacy)
        if self.config.strip_background_path:
            bg_path = Path(self.config.strip_background_path)
            if bg_path.exists():
                try:
                    bg_img = Image.open(bg_path).convert("RGB")
                    bg_img = self._resize_cover(bg_img, width, height)
                    return bg_img
                except Exception:
                    pass  # Fall back to solid color

        # Create solid color background
        img = Image.new("RGB", (width, height), self.config.background_color)

        # Apply gradient if configured
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

    def _resize_cover(self, img: Image.Image, target_width: int, target_height: int) -> Image.Image:
        """Resize image to cover target dimensions (like CSS background-size: cover)."""
        img_ratio = img.width / img.height
        target_ratio = target_width / target_height

        if img_ratio > target_ratio:
            # Image is wider, scale by height
            new_height = target_height
            new_width = int(target_height * img_ratio)
        else:
            # Image is taller, scale by width
            new_width = target_width
            new_height = int(target_width / img_ratio)

        # Resize and crop to center
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Crop to target size (centered)
        left = (new_width - target_width) // 2
        top = (new_height - target_height) // 2
        return img.crop((left, top, left + target_width, top + target_height))

    def _calculate_icon_size(self, radius: float) -> int:
        """
        Calculate appropriate icon size based on stamp radius.
        
        The icon should fit comfortably inside the stamp with some padding.
        We use ~60% of the diameter to leave room for the border and visual breathing room.
        """
        # Icon size is 60% of diameter (or 120% of radius)
        # This leaves ~20% padding on each side inside the stamp
        icon_size = int(radius * 1.2)
        
        # Ensure minimum icon size for visibility
        return max(icon_size, 16)

    def _draw_stamp(
        self,
        img: Image.Image,
        draw: ImageDraw.Draw,
        circle: CirclePosition,
        filled: bool,
        is_last: bool,
        border_width: int,
    ) -> None:
        """Draw a stamp circle with optional icon."""
        x = int(circle.center_x)
        y = int(circle.center_y)
        radius = int(circle.radius)
        
        fill_color = (
            self.config.stamp_filled_color if filled else self.config.stamp_empty_color
        )

        # Draw the circle background
        draw.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            fill=fill_color,
            outline=self.config.stamp_border_color,
            width=border_width,
        )

        # Draw icon inside if filled
        if filled:
            icon_name = self.config.reward_icon if is_last else self.config.stamp_icon
            icon_size = self._calculate_icon_size(circle.radius)
            icon_img = self._load_icon(icon_name, self.config.icon_color, icon_size)

            if icon_img:
                # Center icon in stamp
                paste_x = x - icon_size // 2
                paste_y = y - icon_size // 2

                # Convert main image to RGBA if needed for proper alpha compositing
                if img.mode != "RGBA":
                    rgba_img = img.convert("RGBA")
                    rgba_img.paste(icon_img, (paste_x, paste_y), icon_img)
                    # Convert back and copy to original
                    rgb_img = rgba_img.convert("RGB")
                    img.paste(rgb_img)
                else:
                    img.paste(icon_img, (paste_x, paste_y), icon_img)
            else:
                # Fallback: draw inner accent circle if no icon available
                inner_radius = int(radius * 0.35)
                accent_color = (50, 30, 10)  # Dark accent for contrast
                draw.ellipse(
                    [x - inner_radius, y - inner_radius, x + inner_radius, y + inner_radius],
                    fill=accent_color,
                )

    def _paste_custom_icon(
        self,
        img: Image.Image,
        circle: CirclePosition,
        filled: bool,
    ) -> bool:
        """Paste a custom stamp icon. Returns True if successful."""
        icon = self._custom_filled if filled else self._custom_empty
        if icon is None:
            return False

        x = int(circle.center_x)
        y = int(circle.center_y)
        radius = int(circle.radius)

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
        stamp_area_height = (self.config.stamp_area_height * scale) // 3
        min_padding = (self.config.min_padding * scale) // 3

        # Clamp stamps to valid range
        stamps = max(0, min(stamps, self.config.total_stamps))

        # Create background (full height)
        img = self._create_background(width, height)
        draw = ImageDraw.Draw(img)

        # Calculate the vertical offset to center stamps in the stamp area
        # The stamp area starts from the bottom of the image
        stamp_area_offset = height - stamp_area_height

        # Calculate circle layout for the stamp area
        layout = calculate_circle_layout(
            count=self.config.total_stamps,
            canvas_width=width,
            canvas_height=stamp_area_height,
            min_padding=min_padding
        )

        # Calculate border width proportional to radius
        border_width = max(1, int(layout.radius / 20)) if layout.radius > 0 else 1

        # Draw stamps
        for circle in layout.circles:
            # Offset Y position to account for stamp area position
            adjusted_circle = CirclePosition(
                center_x=circle.center_x,
                center_y=circle.center_y + stamp_area_offset,
                radius=circle.radius,
                row=circle.row,
                index=circle.index
            )
            
            filled = circle.index < stamps
            is_last = (circle.index == self.config.total_stamps - 1)

            # Try custom icons first (legacy support)
            if filled and self._custom_filled:
                self._paste_custom_icon(img, adjusted_circle, True)
            elif not filled and self._custom_empty:
                self._paste_custom_icon(img, adjusted_circle, False)
            else:
                # Use stamp drawing with predefined icons
                self._draw_stamp(img, draw, adjusted_circle, filled, is_last, border_width)

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
