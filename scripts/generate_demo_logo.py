#!/usr/bin/env python3
"""
One-time script to generate and upload demo logo for Google Wallet.

Run inside the backend container:
    docker exec -it fidelity-backend-1 python -m scripts.generate_demo_logo
"""

import sys
from pathlib import Path

# Add the app to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cairosvg
from app.services.storage import StorageService


DEMO_LOGO_PATH = "stampeo/demo/logo.png"

# Stampeo logo SVG with orange fill
STAMPEO_SVG = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="200" height="200" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path
        clip-rule="evenodd"
        d="M12.0799 24L4 19.2479L9.95537 8.75216L18.04 13.4961L18.0446 4H29.9554L29.96 13.4961L38.0446 8.75216L44 19.2479L35.92 24L44 28.7521L38.0446 39.2479L29.96 34.5039L29.9554 44H18.0446L18.04 34.5039L9.95537 39.2479L4 28.7521L12.0799 24Z"
        fill="#f97316"
        fill-rule="evenodd"
    />
</svg>
'''


def generate_logo() -> bytes:
    """Convert Stampeo SVG to PNG."""
    return cairosvg.svg2png(
        bytestring=STAMPEO_SVG.encode(),
        output_width=200,
        output_height=200,
    )


def main():
    """Generate and upload the demo logo."""
    print("Converting Stampeo SVG to PNG...")
    logo_data = generate_logo()
    print(f"  Logo size: {len(logo_data)} bytes")

    print("Uploading to Supabase Storage...")
    storage = StorageService()
    url = storage.upload_file(
        bucket=storage.BUSINESSES_BUCKET,
        path=DEMO_LOGO_PATH,
        file_data=logo_data,
        content_type="image/png",
    )

    print("\n" + "=" * 60)
    print("Demo logo generated successfully!")
    print("=" * 60)
    print(f"\nURL: {url}")

    return url


if __name__ == "__main__":
    main()
