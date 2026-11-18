from django.conf import settings
from django.db import models


class SecretReveal(models.Model):
    """One look at a secret's value: who, when and how. Written every time a value is shown, copied or exported."""

    class Action(models.TextChoices):
        REVEAL = "reveal", "Revealed"
        COPY = "copy", "Copied"
        EXPORT = "export", "Copied in a .env"

    secret = models.ForeignKey("projects.ProjectSecret", on_delete=models.CASCADE, related_name="reveals")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=10, choices=Action.choices)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-at",)

    def __str__(self):
        return f"{self.get_action_display()} by {self.user} at {self.at:%d/%m/%Y %H:%M}"
