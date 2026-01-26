#!/usr/bin/env python3
"""
Generate placeholder pass assets for the loyalty card.
Run this once before starting the server.
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path


def create_icon(size: int, filename: str, output_dir: Path):
    """Create a coffee cup icon."""
    img = Image.new("RGBA", (size, size), (139, 90, 43, 255))  # Brown background
    draw = ImageDraw.Draw(img)

    # Draw a simple coffee cup shape
    cup_width = int(size * 0.6)
    cup_height = int(size * 0.5)
    cup_left = (size - cup_width) // 2
    cup_top = int(size * 0.35)

    # Cup body
    draw.rectangle(
        [cup_left, cup_top, cup_left + cup_width, cup_top + cup_height],
        fill=(255, 255, 255, 255),
        outline=(80, 50, 20, 255),
        width=max(1, size // 30),
    )

    # Cup handle
    handle_radius = int(size * 0.12)
    handle_x = cup_left + cup_width
    handle_y = cup_top + cup_height // 3
    draw.arc(
        [handle_x, handle_y, handle_x + handle_radius * 2, handle_y + handle_radius * 2],
        start=-90,
        end=90,
        fill=(255, 255, 255, 255),
        width=max(1, size // 20),
    )

    # Steam lines
    steam_color = (255, 255, 255, 180)
    for i, x_offset in enumerate([-0.15, 0, 0.15]):
        x = size // 2 + int(size * x_offset)
        y_start = cup_top - int(size * 0.05)
        y_end = cup_top - int(size * 0.2)
        draw.line([(x, y_start), (x + 2, y_end)], fill=steam_color, width=max(1, size // 20))

    img.save(output_dir / filename)
    print(f"Created {filename} ({size}x{size})")


def create_logo(width: int, height: int, filename: str, output_dir: Path):
    """Create a logo with business name."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))  # Transparent
    draw = ImageDraw.Draw(img)

    # Try to use a font, fall back to default
    font_size = int(height * 0.6)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except (IOError, OSError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except (IOError, OSError):
            font = ImageFont.load_default()

    text = "COFFEE"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (width - text_width) // 2
    y = (height - text_height) // 2

    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)

    img.save(output_dir / filename)
    print(f"Created {filename} ({width}x{height})")


def main():
    output_dir = Path(__file__).parent / "pass_assets"
    output_dir.mkdir(exist_ok=True)

    # Create icons at different resolutions
    create_icon(29, "icon.png", output_dir)
    create_icon(58, "icon@2x.png", output_dir)
    create_icon(87, "icon@3x.png", output_dir)

    # Create logos
    create_logo(160, 50, "logo.png", output_dir)
    create_logo(320, 100, "logo@2x.png", output_dir)

    print("\nPass assets created successfully!")
    print(f"Location: {output_dir}")


if __name__ == "__main__":
    main()
