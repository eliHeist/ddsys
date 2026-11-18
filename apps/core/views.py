from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import aget_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core import services
from apps.core.forms import CompanySettingsForm, StaffCreateForm, StaffEditForm
from apps.core.http import (arender, avalidate, error_response, form_errors, form_page, hx_redirect, redirect_with_message,
                            service_errors, staff_required)
from apps.core.models import CompanySettings, StaffProfile

ADMIN = (StaffProfile.Role.ADMIN,)


@staff_required(*ADMIN)
async def company(request):
    return await form_page(
        request, form_class=CompanySettingsForm, instance=await CompanySettings.aload(),
        success_url=reverse("core:company"), title="Company settings",
        extra={"subtitle": "Printed on quotations, invoices and receipts."})


@staff_required(*ADMIN)
async def staff_list(request):
    people = [s async for s in StaffProfile.objects.select_related("user")]
    return await arender(request, "core/staff_list.html", {"people": people})


@staff_required(*ADMIN)
@service_errors
async def staff_create(request):
    form = StaffCreateForm(request.POST or None)
    if request.method == "POST":
        if not await avalidate(form):
            return await error_response(request, form_errors(form))
        profile = await services.create_staff(request.actor, base_url=request.build_absolute_uri("/"), **form.cleaned_data)
        return redirect_with_message(request, reverse("core:staff"),
                                     f"{profile.user.first_name} added. We've emailed {profile.user.email} a link to choose their password.")
    return await arender(request, "core/form.html", {
        "form": form, "title": "Add a staff member", "cancel_url": reverse("core:staff"), "submit": "Add and send invite",
        "subtitle": "They get an email with their details and a link to choose their own password."})


@staff_required(*ADMIN)
@require_POST
@service_errors
async def staff_invite(request, pk):
    profile = await services.resend_invite(await aget_object_or_404(StaffProfile, pk=pk), request.actor,
                                           base_url=request.build_absolute_uri("/"))
    return redirect_with_message(request, reverse("core:staff"), f"New sign-in link sent to {profile.user.email}.")


@staff_required(*ADMIN)
async def staff_edit(request, pk):
    profile = await StaffProfile.objects.select_related("user").aget(pk=pk)
    return await form_page(request, form_class=StaffEditForm, instance=profile, success_url=reverse("core:staff"),
                           title=f"Edit {profile.user.get_full_name() or profile.user.email}",
                           cancel_url=reverse("core:staff"))


@staff_required()
async def media_file(request, path):
    """Uploaded files (expense receipts, the company logo), for signed-in staff only. Django serves them itself, so
    they are never public, even with no web server in front configured for /media/."""
    root = Path(settings.MEDIA_ROOT).resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise Http404
    return FileResponse(target.open("rb"), filename=target.name, as_attachment=request.GET.get("download") == "1")
