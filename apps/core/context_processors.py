from django.conf import settings
from django.urls import reverse

from . import permissions as p

# (group title, [(label, url name, icon, allowed roles or None for everyone, exact-match?)])
NAV = [
    ("Work", [
        ("Dashboard", "reports:dashboard", "home", None, True),
        ("Clients", "clients:list", "users", None, False),
        ("Projects", "projects:list", "jobs", None, False),
    ]),
    ("Billing", [
        ("Quotations", "billing:quotations", "file", None, False),
        ("Invoices", "billing:invoices", "receipt", None, False),
        ("Receipts", "billing:receipts", "check", p.MONEY, False),
    ]),
    ("Money", [
        ("Accounts", "finance:accounts", "cash", p.MONEY, False),
        ("Expenses", "finance:expenses", "box", p.MONEY, False),
        ("Transactions", "finance:transactions", "chart", p.MONEY, False),
    ]),
    ("Admin", [
        ("Staff", "core:staff", "users", p.ADMINS, False),
        ("Company settings", "core:company", "settings", p.ADMINS, False),
    ]),
]


def nav(request):
    """Sidebar items the signed-in staff member may see. Needs no query: request.staff is set by staff_required."""
    staff = getattr(request, "staff", None)
    if staff is None:
        return {}
    everything = staff.user.is_superuser
    groups = []
    for title, items in NAV:
        shown = [
            {"label": label, "url": url, "icon": icon,
             "active": request.path == url if exact else request.path.startswith(url)}
            for label, name, icon, roles, exact in items
            for url in [reverse(name)]
            if everything or roles is None or staff.role in roles
        ]
        if shown:
            groups.append({"title": title, "items": shown})
    can = {"money": everything or staff.role in p.MONEY, "admin": everything or staff.role in p.ADMINS}
    return {"nav": groups, "can": can}


def brand(request):
    return {"BRAND": getattr(settings, "BRAND_NAME", "Dakdot")}
