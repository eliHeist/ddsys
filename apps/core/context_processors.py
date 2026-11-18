from django.conf import settings
from django.urls import reverse

from . import permissions as p

# (group title, [(label, url name, icon, allowed roles or None for everyone, exact-match?)])
NAV = [
    ("Work", [
        ("Dashboard", "reports:dashboard", "home", None, True),
        ("Clients", "clients:list", "users", None, False),
        ("Projects", "projects:list", "jobs", None, False),
        ("Products", "projects:products", "layers", None, False),
    ]),
    ("Billing", [
        ("Quotations", "billing:quotations", "file", None, False),
        ("Invoices", "billing:invoices", "receipt", None, False),
        ("Subscriptions", "billing:subscriptions", "repeat", None, False),
        ("Receipts", "billing:receipts", "check", p.MONEY, False),
    ]),
    ("Money", [
        ("Accounts", "finance:accounts", "cash", p.MONEY, False),
        ("Expenses", "finance:expenses", "box", p.MONEY, False),
        ("Owed back", "finance:loans", "coins", p.MONEY, False),
        ("Transactions", "finance:transactions", "chart", p.MONEY, False),
    ]),
    ("Admin", [
        ("Staff", "core:staff", "users", p.ADMINS, False),
        ("API keys", "core:api-keys", "settings", p.ADMINS, False),
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
            {"label": label, "url": url, "icon": icon, "exact": exact}
            for label, name, icon, roles, exact in items
            for url in [reverse(name)]
            if everything or roles is None or staff.role in roles
        ]
        if shown:
            groups.append({"title": title, "items": shown})
    # one active item: the longest URL the path starts with (so /projects/products/ is Products, not Projects)
    # a view can say which item it belongs to (request.nav_url), e.g. a product's page lives under /projects/
    path = getattr(request, "nav_url", None) or request.path
    matches = [i for g in groups for i in g["items"]
               if (path == i["url"] if i["exact"] else path.startswith(i["url"]))]
    best = max(matches, key=lambda i: len(i["url"]), default=None)
    for g in groups:
        for i in g["items"]:
            i["active"] = i is best
    can = {"money": everything or staff.role in p.MONEY, "admin": everything or staff.role in p.ADMINS}
    return {"nav": groups, "can": can}


def brand(request):
    return {"BRAND": getattr(settings, "BRAND_NAME", "Dakdot")}
