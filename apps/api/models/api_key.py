import hashlib
import secrets

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel

KEY_PREFIX = "dak"


def hash_key(raw_key):
    """Keys are long random strings, so a plain SHA-256 is enough; only the hash is stored."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def new_raw_key():
    """dak_<8 hex>_<43 url-safe chars>. The middle part is stored in clear to find the key and show it in lists."""
    lookup = secrets.token_hex(4)
    return lookup, f"{KEY_PREFIX}_{lookup}_{secrets.token_urlsafe(32)}"


class ApiKey(TimeStampedModel):
    """Lets one product's app read that product's records (subscribers, invoices, payments) through the API.

    The full key is shown once, when it is made (api.services.create_api_key); afterwards only its `lookup` part
    is visible. A key can only ever see its own product's records. Revoking is immediate and permanent.
    """

    name = models.CharField(max_length=80, help_text='Where it is used, e.g. "DotScholar production server"')
    product = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="api_keys",
                                limit_choices_to={"kind": "product"})
    lookup = models.CharField(max_length=16, unique=True)
    key_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("revoked_at", "-created_at")
        verbose_name = "API key"

    def __str__(self):
        # Used by the throttle as this key's identity: stable and not secret.
        return f"api-key:{self.lookup}"

    @property
    def masked(self):
        return f"{KEY_PREFIX}_{self.lookup}_…"

    @property
    def is_active(self):
        return self.revoked_at is None
