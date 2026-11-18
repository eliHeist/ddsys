from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from apps.api.api import api
from apps.core.views import media_file
from dakdot.appsConfig import getAppUrls

urlpatterns = [
    path("", RedirectView.as_view(url="/app/", permanent=False)),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/mfa/", include("allauth.mfa.urls")),
    path("api/v1/", api.urls),  # apps/api: the API for our products' apps
]

urlpatterns += getAppUrls()

if "debug_toolbar" in settings.INSTALLED_APPS:
    from debug_toolbar.toolbar import debug_toolbar_urls
    urlpatterns += debug_toolbar_urls()

# uploads (expense receipts, the logo): signed-in staff only, in development and production alike
urlpatterns += [path(f"{settings.MEDIA_URL.strip('/')}/<path:path>", media_file, name="media")]
