from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("<slug:kind>/<int:pk>.pdf", views.pdf, name="pdf"),
]
