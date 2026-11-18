from django.urls import path

from apps.api import views as api_views

from . import views

app_name = "core"

urlpatterns = [
    path("company/", views.company, name="company"),
    path("staff/", views.staff_list, name="staff"),
    path("staff/new/", views.staff_create, name="staff-new"),
    path("staff/<int:pk>/", views.staff_edit, name="staff-edit"),
    path("staff/<int:pk>/invite/", views.staff_invite, name="staff-invite"),
    path("api-keys/", api_views.key_list, name="api-keys"),
    path("api-keys/new/", api_views.key_create, name="api-key-new"),
    path("api-keys/<int:pk>/revoke/", api_views.key_revoke, name="api-key-revoke"),
]
