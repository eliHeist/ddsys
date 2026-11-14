from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("company/", views.company, name="company"),
    path("staff/", views.staff_list, name="staff"),
    path("staff/new/", views.staff_create, name="staff-new"),
    path("staff/<int:pk>/", views.staff_edit, name="staff-edit"),
]
