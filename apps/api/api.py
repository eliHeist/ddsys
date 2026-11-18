"""The Dakdot API (django-ninja), read-only, for Dakdot's own products' apps.

Every request (except /health) needs `Authorization: Bearer <key>`; a key belongs to one product and sees only that
product's subscribers, invoices and receipts. Keys are made by admins under Admin > API keys. Lists are paginated
with `?limit=&offset=`. Mounted at /api/v1/ by dakdot/urls.py. Docs (Swagger UI) at /api/v1/docs, for signed-in admins only.
"""

from django.conf import settings
from ninja import NinjaAPI
from ninja.throttling import AuthRateThrottle

from .auth import ApiKeyAuth
from .docs import admins_only
from .routers import customers, invoices, product, receipts, subscriptions

api = NinjaAPI(
    title="Dakdot API",
    version="1",
    description=__doc__,
    urls_namespace="api-v1",
    auth=ApiKeyAuth(),
    throttle=[AuthRateThrottle(settings.API_RATE_LIMIT)],
    docs_url="/docs" if settings.API_DOCS_ENABLED else None,
    docs_decorator=admins_only,
)

for module in (product, customers, subscriptions, invoices, receipts):
    api.add_router("/", module.router)
