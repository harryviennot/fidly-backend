"""Business info rendering for wallet pass back fields.

Converts structured business info (hours, website, phone, email, address)
stored in businesses.settings.business_info into formatted PassField dicts
ready for Apple/Google Wallet passes.
"""

from __future__ import annotations

BUSINESS_INFO_TYPES = ["hours", "website", "phone", "email", "address", "custom"]

LABELS: dict[str, dict[str, str]] = {
    "hours": {"en": "Store Hours", "fr": "Horaires d'ouverture"},
    "website": {"en": "Website", "fr": "Site web"},
    "phone": {"en": "Phone", "fr": "Téléphone"},
    "email": {"en": "Email", "fr": "Email"},
    "address": {"en": "Address", "fr": "Adresse"},
}

DAY_NAMES: dict[str, dict[str, str]] = {
    "Mon": {"en": "Mon", "fr": "Lun"},
    "Tue": {"en": "Tue", "fr": "Mar"},
    "Wed": {"en": "Wed", "fr": "Mer"},
    "Thu": {"en": "Thu", "fr": "Jeu"},
    "Fri": {"en": "Fri", "fr": "Ven"},
    "Sat": {"en": "Sat", "fr": "Sam"},
    "Sun": {"en": "Sun", "fr": "Dim"},
}

CLOSED_TEXT: dict[str, str] = {"en": "Closed", "fr": "Fermé"}


def _get_label(info_type: str, locale: str) -> str:
    """Get the translated label for a business info type."""
    return LABELS.get(info_type, {}).get(locale) or LABELS.get(info_type, {}).get("en", info_type)


def _translate_day_range(days: str, locale: str) -> str:
    """Translate day abbreviations in a day range string.

    Handles formats like "Mon-Fri", "Sat", "Mon-Wed, Fri".
    """
    if locale == "en":
        return days

    result = days
    for en_day, translations in DAY_NAMES.items():
        localized = translations.get(locale, en_day)
        result = result.replace(en_day, localized)
    return result


def _format_time(time_str: str, locale: str) -> str:
    """Format a time string (HH:MM) for display.

    English: 9am, 6pm, 12pm
    French: 9h, 18h, 12h
    """
    try:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return time_str

    if locale == "fr":
        if minute:
            return f"{hour}h{minute:02d}"
        return f"{hour}h"

    # English: 12-hour format
    if hour == 0:
        h, suffix = 12, "am"
    elif hour < 12:
        h, suffix = hour, "am"
    elif hour == 12:
        h, suffix = 12, "pm"
    else:
        h, suffix = hour - 12, "pm"

    if minute:
        return f"{h}:{minute:02d}{suffix}"
    return f"{h}{suffix}"


def _render_hours(data: dict, locale: str) -> str:
    """Render store hours schedule as formatted text."""
    schedule = data.get("schedule", [])
    if not schedule:
        return ""

    lines = []
    for entry in schedule:
        days = _translate_day_range(entry.get("days", ""), locale)
        if entry.get("closed"):
            closed = CLOSED_TEXT.get(locale, "Closed")
            lines.append(f"{days}: {closed}")
        else:
            open_time = _format_time(entry.get("open", ""), locale)
            close_time = _format_time(entry.get("close", ""), locale)
            lines.append(f"{days}: {open_time}-{close_time}")
    return "\n".join(lines)


def _render_website(data: dict, _locale: str) -> str:
    return data.get("url", "")


def _render_phone(data: dict, _locale: str) -> str:
    return data.get("number", "")


def _render_email(data: dict, _locale: str) -> str:
    return data.get("email", "")


def _render_address(data: dict, _locale: str) -> str:
    return data.get("address", "")


def _render_custom(data: dict, _locale: str) -> str:
    return data.get("value", "")


_RENDERERS: dict[str, callable] = {
    "hours": _render_hours,
    "website": _render_website,
    "phone": _render_phone,
    "email": _render_email,
    "address": _render_address,
    "custom": _render_custom,
}


def render_business_info(
    business_info: list[dict],
    locale: str = "fr",
) -> list[dict]:
    """Render business info entries into PassField-compatible dicts.

    Args:
        business_info: List of business info entries from business.settings.business_info
        locale: Target locale for labels and formatted values

    Returns:
        List of dicts with {key, label, value} ready for pass back_fields
    """
    fields = []
    for entry in business_info:
        info_type = entry.get("type")
        if info_type not in _RENDERERS:
            continue

        data = entry.get("data", {})
        value = _RENDERERS[info_type](data, locale)
        if not value:
            continue

        # Custom entries use the label from data; presets use translated labels
        if info_type == "custom":
            label = data.get("label", "")
        else:
            label = _get_label(info_type, locale)

        if not label:
            continue

        fields.append({
            "key": entry.get("key", f"biz_{info_type}"),
            "label": label,
            "value": value,
        })

    return fields
