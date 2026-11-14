from django.urls import reverse

from apps.core import services
from apps.core.forms import CompanySettingsForm, StaffCreateForm, StaffEditForm
from apps.core.http import arender, avalidate, error_response, form_errors, form_page, hx_redirect, service_errors, staff_required
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
        await services.create_staff(request.actor, **form.cleaned_data)
        return hx_redirect(request, reverse("core:staff"))
    return await arender(request, "core/form.html", {
        "form": form, "title": "Add a staff member", "cancel_url": reverse("core:staff"), "submit": "Add"})


@staff_required(*ADMIN)
async def staff_edit(request, pk):
    profile = await StaffProfile.objects.select_related("user").aget(pk=pk)
    return await form_page(request, form_class=StaffEditForm, instance=profile, success_url=reverse("core:staff"),
                           title=f"Edit {profile.user.get_full_name() or profile.user.email}",
                           cancel_url=reverse("core:staff"))
