import hmac
from datetime import timedelta

from django.utils import timezone
from ninja.security import HttpBearer

from .models.api_key import KEY_PREFIX, hash_key
from .models import ApiKey

TOUCH_EVERY = timedelta(minutes=5)  # how often last_used_at is written, to spare the database


class ApiKeyAuth(HttpBearer):
    """`Authorization: Bearer dak_xxxxxxxx_...`. On success `request.auth` is the ApiKey (with its product).

    `__call__` is async on purpose: django-ninja awaits an async auth callable in async views, and the key lookup
    uses the async ORM. (ninja's own HttpBearer is sync and would hand back an un-awaited coroutine.)
    """

    async def __call__(self, request):
        header = request.headers.get(self.header, "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != self.openapi_scheme or not token:
            return None
        return await self.authenticate(request, token.strip())

    async def authenticate(self, request, token):
        parts = token.split("_", 2)  # the secret part can itself contain "_"
        if len(parts) != 3 or parts[0] != KEY_PREFIX:
            return None
        key = await ApiKey.objects.select_related("product").filter(lookup=parts[1], revoked_at__isnull=True).afirst()
        if key is None or not hmac.compare_digest(key.key_hash, hash_key(token)):
            return None
        now = timezone.now()
        if key.last_used_at is None or now - key.last_used_at > TOUCH_EVERY:
            await ApiKey.objects.filter(pk=key.pk).aupdate(last_used_at=now)
        return key
