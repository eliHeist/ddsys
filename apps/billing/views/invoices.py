from django.shortcuts import aget_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.billing import selectors
from apps.billing.forms import PaymentForm, payment_dialog, void_dialog
from apps.billing.models import Invoice
from apps.billing.services import invoices, receipts
from apps.core.http import (arender, avalidate, error_response, form_errors, hx_redirect, redirect_with_message, paginate, service_errors,
                            staff_required, wants_partial)
from apps.core.permissions import MONEY
from apps.finance.models import Account

from .editor import editor_page


@staff_required()
async def invoice_list(request):
    status, query = request.GET.get("status", ""), request.GET.get("q", "").strip()
    page = await paginate(selectors.invoices_for(status, query), request)
    template = "billing/partials/_invoice_rows.html" if wants_partial(request, "invoice-rows") else "billing/invoice_list.html"
    return await arender(request, template, {"page_obj": page, "q": query, "status": status,
                                             "outstanding": await selectors.outstanding()})


@staff_required()
async def invoice_detail(request, pk):
    invoice = await selectors.invoice_detail(pk)
    accounts = [a async for a in Account.objects.filter(is_active=True)]
    return await arender(request, "billing/invoice_detail.html", {
        "doc": invoice,
        "payment_dialog": payment_dialog(invoice, accounts) if invoice.is_open else None,
        "void_dialog": void_dialog(f"Void {invoice.label}", reverse("billing:invoice-void", args=[pk]), "The invoice"),
    })


@staff_required()
@service_errors
async def invoice_create(request):
    return await editor_page(request, "invoice", create=invoices.create_invoice, update=None)


@staff_required()
@service_errors
async def invoice_edit(request, pk):
    invoice = await aget_object_or_404(Invoice, pk=pk)
    return await editor_page(request, "invoice", document=invoice, create=None, update=invoices.update_invoice)


def _back(request, pk, message):
    return redirect_with_message(request, reverse("billing:invoice", args=[pk]), message)


@staff_required(*MONEY)
@require_POST
@service_errors
async def invoice_issue(request, pk):
    await invoices.issue_invoice(await aget_object_or_404(Invoice, pk=pk), request.actor)
    return _back(request, pk, "Invoice issued. Download the PDF to send it.")


@staff_required(*MONEY)
@require_POST
@service_errors
async def invoice_void(request, pk):
    await invoices.void_invoice(await aget_object_or_404(Invoice, pk=pk), request.actor, reason=request.POST.get("reason", ""))
    return _back(request, pk, "Invoice voided.")


@staff_required()
@require_POST
@service_errors
async def invoice_delete(request, pk):
    await invoices.delete_draft(await aget_object_or_404(Invoice, pk=pk), request.actor)
    return hx_redirect(request, reverse("billing:invoices"))


@staff_required(*MONEY)
@require_POST
@service_errors
async def invoice_pay(request, pk):
    invoice = await aget_object_or_404(Invoice, pk=pk)
    form = PaymentForm(request.POST)
    if not await avalidate(form):
        return await error_response(request, form_errors(form))
    receipt = await receipts.record_payment(invoice, request.actor, **form.cleaned_data)
    return redirect_with_message(request, reverse("billing:receipt", args=[receipt.pk]), f"Payment recorded: {receipt.number}.")
