from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Project


@admin.register(Project)
class ProjectAdmin(SimpleHistoryAdmin):
    list_display = ("title", "client", "status", "due_date")
    list_filter = ("status",)
    search_fields = ("title", "client__name")
