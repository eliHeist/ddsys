from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="list"),
    path("products/", views.product_list, name="products"),
    path("new/", views.project_create, name="new"),
    path("<int:pk>/", views.project_detail, name="detail"),
    path("<int:pk>/edit/", views.project_edit, name="edit"),
    path("<int:pk>/secrets/new/", views.secret_new, name="secret-new"),
    path("<int:pk>/secrets/env/", views.secrets_env, name="secrets-env"),
    path("<int:pk>/secrets/<int:secret_pk>/edit/", views.secret_edit, name="secret-edit"),
    path("<int:pk>/secrets/<int:secret_pk>/value/", views.secret_value, name="secret-value"),
    path("<int:pk>/secrets/<int:secret_pk>/delete/", views.secret_delete, name="secret-delete"),
]
