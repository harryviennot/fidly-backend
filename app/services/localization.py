"""
System translations for wallet passes.

Maps system-generated strings to supported locales.
Business-provided content (organization name, field labels/values) is handled
separately via the translations JSONB column on card_designs.
"""

SUPPORTED_LOCALES = ("fr", "en")

# System strings used in pass generation (not editable by businesses)
_SYSTEM_STRINGS: dict[str, dict[str, str]] = {
    "stamps_label": {
        "fr": "TAMPONS",
        "en": "STAMPS",
    },
    "view_loyalty_card": {
        "fr": "Voir la carte de fidélité",
        "en": "View Loyalty Card",
    },
    "loyalty_card_description": {
        "fr": "Carte de fidélité",
        "en": "Loyalty Card",
    },
    "stamps_content_description": {
        "fr": "{count}/{total} tampons",
        "en": "{count}/{total} stamps",
    },
    "logo_content_description": {
        "fr": "Logo {business}",
        "en": "{business} logo",
    },
}


def get_system_string(key: str, locale: str, **kwargs: str | int) -> str:
    """Return a translated system string with placeholder substitution.

    Falls back to English if the locale or key is not found.
    """
    strings = _SYSTEM_STRINGS.get(key, {})
    template = strings.get(locale) or strings.get("en", key)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template
