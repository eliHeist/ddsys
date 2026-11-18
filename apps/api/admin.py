from django.contrib import admin

from .models import ApiKey


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    """Read-only here: keys are made and revoked in the app (Admin > API keys), which shows the key once."""

    list_display = ("name", "product", "lookup", "last_used_at", "revoked_at")
    readonly_fields = ("name", "product", "lookup", "key_hash", "created_by", "last_used_at", "revoked_at")

    def has_add_permission(self, request):
        return False
