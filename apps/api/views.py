"""Admin pages for API keys (mounted under app/settings/ by core.urls). The API itself is in api.py."""

from django.shortcuts import aget_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.http import (arender, avalidate, error_response, form_errors, redirect_with_message, service_errors,
                            staff_required)
from apps.core.permissions import ADMINS

from . import services
from .forms import ApiKeyForm
from .models import ApiKey


@staff_required(*ADMINS)
async def key_list(request):
    keys = [k async for k in ApiKey.objects.select_related("product", "created_by")]
    return await arender(request, "api/key_list.html", {"keys": keys, "docs_url": "/api/v1/docs"})


@staff_required(*ADMINS)
@service_errors
async def key_create(request):
    form = ApiKeyForm(request.POST or None)
    if request.method == "POST":
        if not await avalidate(form):
            return await error_response(request, form_errors(form))
        key, raw_key = await services.create_api_key(request.actor, **form.cleaned_data)
        # Rendered straight back (not redirected): the full key exists only in this response.
        return await arender(request, "api/key_created.html", {"key": key, "raw_key": raw_key})
    return await arender(request, "core/form.html", {
        "form": form, "title": "New API key", "submit": "Create key", "cancel_url": reverse("core:api-keys"),
        "subtitle": "The key is shown once. Copy it into the product's server settings."})


@staff_required(*ADMINS)
@require_POST
@service_errors
async def key_revoke(request, pk):
    await services.revoke_api_key(await aget_object_or_404(ApiKey, pk=pk), request.actor)
    return redirect_with_message(request, reverse("core:api-keys"), "Key revoked. Apps using it are cut off now.")
