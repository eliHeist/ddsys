import json
from decimal import Decimal, InvalidOperation

from django import template
from django.conf import settings
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

PILLS = {
    "gray": {"draft", "cancelled", "void", "lead"},
    "blue": {"issued", "active"},
    "amber": {"partial", "on_hold"},
    "green": {"paid", "completed", "accepted", "valid", "ok"},
    "red": {"declined", "overdue"},
}
# A quotation that is issued is waiting on the client: amber, not the blue of an issued invoice.
DOMAIN_OVERRIDES = {("quote", "issued"): "amber"}


# <c-ui.badge> colour names for the pill colours above.
BADGE_COLOURS = {"gray": "ink", "blue": "blue", "amber": "amber", "green": "green", "red": "red"}


def _pill_colour(status, domain=""):
    status = str(status or "").lower()
    return DOMAIN_OVERRIDES.get((domain, status)) or next((c for c, names in PILLS.items() if status in names), "gray")


@register.filter
def status_color(status, domain=""):
    """The <c-ui.badge> colour for a status (used by <c-status>): {{ job.status|status_color }}, or with a
    domain whose colours differ: {{ quote.status|status_color:"quote" }}."""
    return BADGE_COLOURS[_pill_colour(status, domain)]


@register.filter
def money(value, currency=None):
    try:
        amount = Decimal(value or 0)
    except (InvalidOperation, TypeError):
        return value
    return f"{currency or getattr(settings, 'DEFAULT_CURRENCY', 'UGX')} {amount:,.0f}"


@register.filter
def number(value):
    try:
        return f"{Decimal(value or 0):,.0f}"
    except (InvalidOperation, TypeError):
        return value


@register.filter
def initials(user):
    name = (getattr(user, "get_full_name", lambda: "")() or getattr(user, "username", "") or str(user or "?")).strip()
    parts = name.split()
    return (parts[0][0] + parts[-1][0] if len(parts) > 1 else name[:2]).upper()


@register.filter
def jsattr(value):
    """JSON that is safe inside a single-quoted HTML attribute, for Alpine: @click='open({{ cfg|jsattr }})'."""
    text = json.dumps(value, default=str)
    for char, code in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"), ("'", "\\u0027")):
        text = text.replace(char, code)
    return mark_safe(text)


@register.filter
def get_item(mapping, key):
    return mapping.get(key) if hasattr(mapping, "get") else None


ICONS = {
    "home": "M3 11l9-8 9 8M5 10v10h14V10", "jobs": "M9 4h6v3H9zM7 5H5v16h14V5h-2M9 12h6M9 16h4",
    "logout": "M10 4H5v16h5M14 16l4-4-4-4M18 12H9",
    # the Markdown editor's toolbar (cotton/markdown_editor.html)
    "bold": "M7 5h6a3.5 3.5 0 010 7H7zM7 12h7a3.5 3.5 0 010 7H7z", "italic": "M10 5h8M6 19h8M14 5l-4 14",
    "heading": "M6 5v14M18 5v14M6 12h12", "list": "M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01",
    "list-ordered": "M10 6h10M10 12h10M10 18h10M4 5l1.5-1v5M3.5 14.5a1.3 1.3 0 012.4.7L3.5 19H6",
    "quote": "M5 7h5v5H7c0 2 1 3 3 4M14 7h5v5h-3c0 2 1 3 3 4", "minus": "M5 12h14",
    "eye": "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 15a3 3 0 100-6 3 3 0 000 6z",
    "printer": "M7 9V3h10v6M7 17H4v-8h16v8h-3M7 14h10v7H7z",
    "plus": "M12 5v14M5 12h14", "calendar": "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
    "users": "M9 11a3 3 0 100-6 3 3 0 000 6zM3 20c0-3 3-5 6-5s6 2 6 5M17 8a2.5 2.5 0 010 5M21 19c0-2-1.5-3.5-3.5-4",
    "car": "M5 17h14l-1.5-6h-11zM7 17v2M17 17v2M6.5 11l1.5-4h8l1.5 4", "box": "M3 8l9-5 9 5v8l-9 5-9-5zM3 8l9 5 9-5M12 13v8",
    "truck": "M3 7h11v9H3zM14 10h4l3 3v3h-7zM7 19a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM17 19a1.5 1.5 0 100-3 1.5 1.5 0 000 3z",
    "receipt": "M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6", "cash": "M3 7h18v10H3zM12 14a2 2 0 100-4 2 2 0 000 4zM6 10v.01M18 14v.01",
    "chart": "M4 20V10M10 20V4M16 20v-7M22 20H2", "bell": "M6 9a6 6 0 0112 0c0 6 2 7 2 7H4s2-1 2-7zM10 20a2 2 0 004 0",
    "settings": "M12 15a3 3 0 100-6 3 3 0 000 6zM19 12l2 1-2 4-2-1-2 1v2h-4v-2l-2-1-2 1-2-4 2-1v-2L3 9l2-4 2 1 2-1V3h4v2l2 1 2-1 2 4-2 1z",
    "search": "M11 18a7 7 0 100-14 7 7 0 000 14zM21 21l-5-5", "sun": "M12 16a4 4 0 100-8 4 4 0 000 8zM12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5",
    "moon": "M20 14A8 8 0 1110 4a6 6 0 0010 10z", "menu": "M4 6h16M4 12h16M4 18h16", "x": "M6 6l12 12M18 6L6 18",
    "check": "M5 12l5 5 9-10", "chevron": "M6 9l6 6 6-6", "download": "M12 4v11M7 11l5 5 5-5M5 20h14",
    "camera": "M4 8h4l2-3h4l2 3h4v11H4zM12 17a3.5 3.5 0 100-7 3.5 3.5 0 000 7z", "clock": "M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2",
    "alert": "M12 3l10 18H2zM12 10v5M12 18v.01", "wrench": "M14 7a4 4 0 105 5l-8 8-3-3 8-8zM6 17l-2 2", "phone": "M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z",
    "file": "M7 3h7l5 5v13H7zM14 3v5h5", "send": "M4 12l16-8-6 16-3-7z", "edit": "M4 20h4L19 9l-4-4L4 16zM13 7l4 4", "trash": "M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13",
}


@register.simple_tag
def icon(name, size="size-4"):
    path = ICONS.get(name, "")
    return format_html(
        '<svg aria-hidden="true" class="{} shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="{}"/></svg>', size, path)


