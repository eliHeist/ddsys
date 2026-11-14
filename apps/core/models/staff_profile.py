from django.conf import settings
from django.db import models


class StaffProfile(models.Model):
    """What a user may do in the system. Every signed-in user needs an active profile."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        FINANCE = "finance", "Finance"
        STAFF = "staff", "Staff"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)
    phone = models.CharField(max_length=30, blank=True)
    title = models.CharField(max_length=80, blank=True, help_text="Job title, e.g. Designer")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("user__first_name", "user__email")

    def __str__(self):
        return f"{self.user} ({self.get_role_display()})"
