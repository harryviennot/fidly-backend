"""
Service for mapping onboarding card design data to production card_designs format.

Converts hex colors to rgb and sets appropriate defaults.
"""


def hex_to_rgb(hex_color: str) -> str:
    """
    Convert hex color (#RRGGBB) to rgb format (rgb(R, G, B)).

    Args:
        hex_color: Color in hex format, e.g., "#f5f0e8"

    Returns:
        Color in rgb format, e.g., "rgb(245, 240, 232)"
    """
    if not hex_color:
        return "rgb(255, 255, 255)"

    # Remove # prefix if present
    hex_color = hex_color.lstrip("#")

    # Parse hex values
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"rgb({r}, {g}, {b})"
    except (ValueError, IndexError):
        return "rgb(255, 255, 255)"


def get_luminance(hex_color: str) -> float:
    """
    Calculate relative luminance of a color for contrast decisions.

    Args:
        hex_color: Color in hex format, e.g., "#f5f0e8"

    Returns:
        Luminance value between 0 (dark) and 1 (light)
    """
    if not hex_color:
        return 0.0

    hex_color = hex_color.lstrip("#")

    try:
        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255

        # WCAG luminance formula
        return 0.299 * r + 0.587 * g + 0.114 * b
    except (ValueError, IndexError):
        return 0.0


def map_onboarding_to_card_design(
    card_design_data: dict | None,
    business_name: str,
    category: str | None = None,
) -> dict:
    """
    Map onboarding card_design JSONB to CardDesign creation payload.

    Input (from onboarding_progress.card_design):
    {
        "background_color": "#f5f0e8",
        "accent_color": "#334d43",
        "icon_color": "#ffffff",
        "logo_url": "https://...",
        "stamp_icon": "trophy",
        "reward_icon": "sparkle"
    }

    Output (for card_designs table):
    {
        "name": "Default Design",
        "organization_name": business_name,
        "description": "Loyalty card",
        "background_color": "rgb(245, 240, 232)",
        "foreground_color": "rgb(0, 0, 0)",  # auto from luminance
        "label_color": "rgb(255, 255, 255)",
        "stamp_filled_color": "rgb(51, 77, 67)",
        "stamp_empty_color": "rgb(80, 50, 20)",
        "stamp_border_color": "rgb(255, 255, 255)",
        "stamp_icon": "trophy",
        "reward_icon": "sparkle",
        "total_stamps": 10,
    }
    """
    if not card_design_data:
        card_design_data = {}

    # Get colors with defaults
    bg_hex = card_design_data.get("background_color", "#1c1c1e")
    accent_hex = card_design_data.get("accent_color", "#f97316")
    icon_color_hex = card_design_data.get("icon_color", "#ffffff")

    # Convert colors to rgb
    background_color = hex_to_rgb(bg_hex)
    stamp_filled_color = hex_to_rgb(accent_hex)
    label_color = hex_to_rgb(icon_color_hex)

    # Determine foreground (text) color based on background luminance
    luminance = get_luminance(bg_hex)
    if luminance > 0.5:
        # Light background -> dark text
        foreground_color = "rgb(0, 0, 0)"
    else:
        # Dark background -> light text
        foreground_color = "rgb(255, 255, 255)"

    # Get category label for description
    category_labels = {
        "cafe": "Coffee Shop",
        "restaurant": "Restaurant",
        "bakery": "Bakery",
        "retail": "Retail Store",
        "salon": "Beauty & Wellness",
        "fitness": "Fitness Center",
        "services": "Services",
        "other": "Loyalty Card",
    }
    description = category_labels.get(category, "Loyalty Card") if category else "Loyalty Card"

    return {
        "name": "Default Design",
        "organization_name": business_name,
        "description": description,
        "foreground_color": foreground_color,
        "background_color": background_color,
        "label_color": label_color,
        "total_stamps": 10,
        "stamp_filled_color": stamp_filled_color,
        "stamp_empty_color": "rgb(80, 50, 20)",
        "stamp_border_color": "rgb(255, 255, 255)",
        "stamp_icon": card_design_data.get("stamp_icon", "checkmark"),
        "reward_icon": card_design_data.get("reward_icon", "gift"),
    }
