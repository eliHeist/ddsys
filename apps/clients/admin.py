from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Client


@admin.register(Client)
class ClientAdmin(SimpleHistoryAdmin):
    list_display = ("name", "contact_person", "phone", "email", "is_active")
    search_fields = ("name", "contact_person", "phone", "email")
