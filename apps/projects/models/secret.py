from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core import crypto
from apps.core.models import TimeStampedModel


class ProjectSecret(TimeStampedModel):
    """Something private a project needs, kept encrypted (apps.core.crypto). Two kinds:

    - VARIABLE: an API key or setting. title "Stripe live key", name STRIPE_SECRET_KEY, value sk_live_...
    - LOGIN: an account. title "Django admin", name = the username, value = the password, link = the sign-in page.

    Only `value` is secret. Pages never include it: it is fetched when someone reveals or copies it, and each of
    those is written to SecretReveal.
    """

    class Kind(models.TextChoices):
        VARIABLE = "variable", "Variable"
        LOGIN = "login", "Login"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="secrets")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.VARIABLE)
    title = models.CharField(max_length=150)
    name = models.CharField(max_length=255, help_text="The variable's name, or the username")
    encrypted_value = models.TextField(editable=False)
    link = models.URLField(max_length=500, blank=True, help_text="Logins: the page to sign in on")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    history = HistoricalRecords()  # keeps earlier values, still encrypted

    class Meta:
        ordering = ("title", "id")

    def __str__(self):
        return f"{self.title} ({self.project.title})"

    @property
    def value(self):
        return crypto.decrypt(self.encrypted_value) if self.encrypted_value else ""

    @value.setter
    def value(self, text):
        self.encrypted_value = crypto.encrypt(text)

    @property
    def is_login(self):
        return self.kind == self.Kind.LOGIN
