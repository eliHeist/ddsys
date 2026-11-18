from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.async_utils import service
from apps.core.permissions import ADMINS, require_role

from .models import ApiKey
from .models.api_key import hash_key, new_raw_key


@service
@transaction.atomic
def create_api_key(by, *, name, product):
    """Make a key for one product's app. Returns (key, raw_key): show raw_key once, it is not stored."""
    require_role(by, *ADMINS)
    if not product.is_product:
        raise ValidationError("API keys are for our products only.")
    lookup, raw_key = new_raw_key()
    key = ApiKey.objects.create(name=name.strip(), product=product, lookup=lookup, key_hash=hash_key(raw_key),
                                created_by=by)
    return key, raw_key


@service
@transaction.atomic
def revoke_api_key(key, by):
    require_role(by, *ADMINS)
    key = ApiKey.objects.select_for_update().get(pk=key.pk)
    if key.revoked_at:
        raise ValidationError("This key is already revoked.")
    key.revoked_at = timezone.now()
    key.save(update_fields=["revoked_at", "updated_at"])
    return key
