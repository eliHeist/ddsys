from django.shortcuts import aget_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.billing import selectors
from apps.billing.forms import deposit_dialog, void_dialog
from apps.billing.models import Quotation
from apps.billing.services import quotations
from apps.core.permissions import MONEY
from apps.finance.models import Account
from apps.core.http import arender, hx_redirect, redirect_with_message, paginate, service_errors, staff_required, wants_partial

from .editor import editor_page


@staff_required()
async def quotation_list(request):
    status, query = request.GET.get("status", ""), request.GET.get("q", "").strip()
    page = await paginate(selectors.quotations_for(status, query), request)
    template = "billing/partials/_quotation_rows.html" if wants_partial(request, "quotation-rows") else "billing/quotation_list.html"
    return await arender(request, template, {"page_obj": page, "q": query, "status": status})


@staff_required()
async def quotation_detail(request, pk):
    quotation = await selectors.quotation_detail(pk)
    context = {
        "doc": quotation, "invoice": quotation.invoice,
        "deposits": [r async for r in selectors.with_credit(quotation.deposits.order_by("date", "id"))],
        "void_dialog": void_dialog(f"Void {quotation.label}", reverse("billing:quotation-void", args=[pk]), "The quotation"),
    }
    can_take_deposit = quotation.status in (Quotation.Status.ISSUED, Quotation.Status.ACCEPTED)
    if can_take_deposit and (request.actor.is_superuser or request.staff.role in MONEY):
        accounts = [a async for a in Account.objects.filter(is_active=True)]
        context["deposit_dialog"] = deposit_dialog(quotation.client, accounts, quotations=[quotation], quotation=quotation)
    return await arender(request, "billing/quotation_detail.html", context)


@staff_required()
@service_errors
async def quotation_create(request):
    return await editor_page(request, "quotation", create=quotations.create_quotation, update=None)


@staff_required()
@service_errors
async def quotation_edit(request, pk):
    quotation = await aget_object_or_404(Quotation, pk=pk)
    return await editor_page(request, "quotation", document=quotation, create=None, update=quotations.update_quotation)


async def _act(request, pk, action, message, **kwargs):
    quotation = await aget_object_or_404(Quotation, pk=pk)
    result = await action(quotation, request.actor, **kwargs)
    return redirect_with_message(request, reverse("billing:quotation", args=[pk]), message), result


@staff_required()
@require_POST
@service_errors
async def quotation_issue(request, pk):
    return (await _act(request, pk, quotations.issue_quotation, "Quotation issued."))[0]


@staff_required()
@require_POST
@service_errors
async def quotation_decide(request, pk, answer):
    return (await _act(request, pk, quotations.decide_quotation, f"Marked {answer}.", accepted=answer == "accepted"))[0]


@staff_required()
@require_POST
@service_errors
async def quotation_convert(request, pk):
    quotation = await aget_object_or_404(Quotation, pk=pk)
    invoice = await quotations.convert_to_invoice(quotation, request.actor)
    return redirect_with_message(request, reverse("billing:invoice", args=[invoice.pk]), "Draft invoice made from the quotation. Check it, then issue it.")


@staff_required()
@require_POST
@service_errors
async def quotation_void(request, pk):
    reason = request.POST.get("reason", "")
    return (await _act(request, pk, quotations.void_quotation, "Quotation voided.", reason=reason))[0]


@staff_required()
@require_POST
@service_errors
async def quotation_delete(request, pk):
    quotation = await aget_object_or_404(Quotation, pk=pk)
    await quotations.delete_draft(quotation, request.actor)
    return hx_redirect(request, reverse("billing:quotations"))
