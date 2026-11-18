from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Project, ProjectSecret, SecretReveal


@admin.register(Project)
class ProjectAdmin(SimpleHistoryAdmin):
    list_display = ("title", "client", "status", "due_date")
    list_filter = ("status",)
    search_fields = ("title", "client__name")


class RevealInline(admin.TabularInline):
    model = SecretReveal
    extra = 0
    can_delete = False
    readonly_fields = ("action", "user", "at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ProjectSecret)
class ProjectSecretAdmin(admin.ModelAdmin):
    """Read-only here: values stay encrypted. Shows who has looked at each secret. Change secrets in the app."""
    list_display = ("title", "project", "kind", "name", "updated_at")
    list_filter = ("kind",)
    search_fields = ("title", "name", "project__title")
    readonly_fields = ("project", "kind", "title", "name", "link", "created_by", "updated_by", "created_at", "updated_at")
    exclude = ("encrypted_value",)
    inlines = [RevealInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
