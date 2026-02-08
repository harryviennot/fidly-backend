#!/usr/bin/env python3
"""
One-time script to generate and upload demo hero images for Google Wallet.

Run inside the backend container:
    docker exec -it fidelity-backend-1 python -m scripts.generate_demo_heroes
"""

import sys
from pathlib import Path

# Add the app to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.strip_generator import StripImageGenerator, StripConfig
from app.services.storage import StorageService


# Fixed Stampeo demo config (matches DemoPassGenerator colors)
DEMO_CONFIG = StripConfig(
    background_color=(28, 28, 30),  # Stampeo black
    stamp_filled_color=(249, 115, 22),  # Orange stamps
    stamp_empty_color=(45, 45, 50),  # Darker grey empty
    stamp_border_color=(156, 163, 175),  # Demo grey border
    total_stamps=8,
    stamp_icon="checkmark",
    reward_icon="gift",
    icon_color=(255, 255, 255),  # White icons
)

DEMO_HERO_PATH = "stampeo/demo/strips/google"


def generate_demo_heroes():
    """Generate and upload all 9 demo hero images (0-8 stamps)."""
    print("Initializing services...")
    generator = StripImageGenerator(config=DEMO_CONFIG)
    storage = StorageService()

    print(f"Generating {DEMO_CONFIG.total_stamps + 1} hero images...")

    urls = []
    for stamp_count in range(DEMO_CONFIG.total_stamps + 1):  # 0 to 8
        print(f"  Generating hero_{stamp_count}.png...")

        # Generate Google hero image (1032x336)
        hero_data = generator.generate_google_hero(stamp_count)

        # Upload to Supabase Storage
        path = f"{DEMO_HERO_PATH}/hero_{stamp_count}.png"
        url = storage.upload_file(
            bucket=storage.BUSINESSES_BUCKET,
            path=path,
            file_data=hero_data,
            content_type="image/png",
        )
        urls.append(url)
        print(f"    Uploaded: {url}")

    print("\n" + "=" * 60)
    print("Demo hero images generated successfully!")
    print("=" * 60)
    print("\nURLs:")
    for i, url in enumerate(urls):
        print(f"  hero_{i}: {url}")

    return urls


if __name__ == "__main__":
    generate_demo_heroes()
