"""Date display helpers for consistent DD/MM/YY formatting in UI."""

from datetime import datetime


def format_display_date(value: str | None) -> str:
    """Convert common stored date formats to DD/MM/YY for UI display."""
    text = (value or "").strip()
    if not text:
        return "—"

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%d/%m/%y")
        except ValueError:
            continue

    # Preserve values that are not plain dates.
    return text


def format_display_datetime(value: str | None) -> str:
    """Convert common stored datetime formats to DD/MM/YY HH:MM for UI display."""
    text = (value or "").strip()
    if not text:
        return "—"

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt == "%Y-%m-%d":
                return parsed.strftime("%d/%m/%y")
            return parsed.strftime("%d/%m/%y %H:%M")
        except ValueError:
            continue

    return text
