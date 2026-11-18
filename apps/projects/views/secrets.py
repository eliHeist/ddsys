"""A project's secrets: API keys, settings and logins, kept encrypted (models.ProjectSecret).

Every staff member can see them and add or change them; only admins delete. Values are never part of a page:
the browser asks for one when someone reveals or copies it (secret_value), and each ask is logged."""
from functools import partial

from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import aget_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.http import form_page, staff_required
from apps.core.permissions import ADMINS

from ..dotenv import env_file
from ..forms import SecretForm
from ..models import Project, ProjectSecret, SecretReveal

Kind = ProjectSecret.Kind
NO_STORE = {"Cache-Control": "no-store"}


def _back(project_pk):
    return reverse("projects:detail", args=[project_pk]) + "#secrets"


@staff_required()
async def secret_new(request, pk):
    project = await aget_object_or_404(Project, pk=pk)
    kind = Kind.LOGIN if request.GET.get("kind") == Kind.LOGIN else Kind.VARIABLE
    return await form_page(
        request, form_class=partial(SecretForm, project=project, kind=kind, user=request.actor),
        title=f"New {Kind(kind).label.lower()} · {project.title}", cancel_url=_back(pk), success_url=_back(pk))


@staff_required()
async def secret_edit(request, pk, secret_pk):
    secret = await aget_object_or_404(ProjectSecret.objects.select_related("project"), pk=secret_pk, project_id=pk)
    return await form_page(
        request, form_class=partial(SecretForm, project=secret.project, kind=secret.kind, user=request.actor),
        instance=secret, title=f"Edit {secret.title}", cancel_url=_back(pk), success_url=_back(pk))


@staff_required()
@require_POST
async def secret_value(request, pk, secret_pk):
    """The value of one secret, as JSON, for the reveal and copy buttons. Logged."""
    secret = await aget_object_or_404(ProjectSecret, pk=secret_pk, project_id=pk)
    action = SecretReveal.Action.COPY if request.POST.get("action") == "copy" else SecretReveal.Action.REVEAL
    await SecretReveal.objects.acreate(secret=secret, user=request.actor, action=action)
    return JsonResponse({"value": secret.value}, headers=NO_STORE)


@staff_required()
@require_POST
async def secrets_env(request, pk):
    """All the project's variables as the text of a .env file, for "Copy .env". Logged for each variable."""
    variables = [s async for s in ProjectSecret.objects.filter(project_id=pk, kind=Kind.VARIABLE).order_by("name")]
    await SecretReveal.objects.abulk_create(
        SecretReveal(secret=s, user=request.actor, action=SecretReveal.Action.EXPORT) for s in variables)
    return JsonResponse({"value": env_file(variables)}, headers=NO_STORE)


@staff_required(*ADMINS)
@require_POST
async def secret_delete(request, pk, secret_pk):
    secret = await aget_object_or_404(ProjectSecret, pk=secret_pk, project_id=pk)
    await secret.adelete()
    messages.success(request, f"Deleted {secret.title}.")
    # Reload rather than redirect: the dialog posts from this same page, and a redirect to it plus "#secrets"
    # would only scroll. A reload keeps the scroll position and shows the message.
    return HttpResponse(status=204, headers={"HX-Refresh": "true"})
