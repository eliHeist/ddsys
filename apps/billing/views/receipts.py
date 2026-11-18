from django.shortcuts import aget_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.billing import selectors
from apps.billing.forms import ApplyCreditForm, DepositForm, receipt_apply_dialog, void_dialog
from apps.billing.models import Allocation, Invoice, Receipt
from apps.billing.services import receipts
from apps.clients.models import Client
from apps.core.http import (arender, avalidate, error_response, form_errors, paginate, redirect_with_message,
                            service_errors, staff_required, wants_partial)
from apps.core.permissions import MONEY


@staff_required(*MONEY)
async def receipt_list(request):
    query = request.GET.get("q", "").strip()
    page = await paginate(selectors.receipts_for(query), request)
    template = "billing/partials/_receipt_rows.html" if wants_partial(request, "receipt-rows") else "billing/receipt_list.html"
    return await arender(request, template, {"page_obj": page, "q": query})


@staff_required()
async def receipt_detail(request, pk):
    receipt = await selectors.receipt_detail(pk)
    context = {
        "receipt": receipt,
        "void_dialog": void_dialog(f"Void {receipt.number}", reverse("billing:receipt-void", args=[pk]), "The receipt")
        | {"message": "The money comes out of the account again, and every invoice it paid owes that part again. "
                      "The receipt keeps its number, marked void."},
    }
    if receipt.status == Receipt.Status.VALID and receipt.credit > 0:
        open_invoices = [i async for i in Invoice.objects.filter(client_id=receipt.client_id, status__in=Invoice.OPEN)
                         .order_by("date", "id")]
        context |= {"open_invoices": open_invoices,
                    "apply_dialog": receipt_apply_dialog(receipt, open_invoices) if open_invoices else None}
    return await arender(request, "billing/receipt_detail.html", context)


@staff_required(*MONEY)
@require_POST
@service_errors
async def receipt_void(request, pk):
    receipt = await aget_object_or_404(Receipt, pk=pk)
    await receipts.void_receipt(receipt, request.actor, reason=request.POST.get("reason", ""))
    return redirect_with_message(request, reverse("billing:receipt", args=[pk]), "Receipt voided.")


@staff_required(*MONEY)
@require_POST
@service_errors
async def deposit_new(request, client_pk):
    """Money from a client before its invoice exists (the deposit dialog on the client's and quotations' pages)."""
    client = await aget_object_or_404(Client, pk=client_pk)
    form = DepositForm(request.POST)
    if not await avalidate(form):
        return await error_response(request, form_errors(form))
    receipt = await receipts.record_deposit(client, request.actor, **form.cleaned_data)
    return redirect_with_message(request, reverse("billing:receipt", args=[receipt.pk]),
                                 f"Deposit recorded: {receipt.number}. It is {client.name}'s credit until applied.")


@staff_required(*MONEY)
@require_POST
@service_errors
async def receipt_apply(request, pk):
    """Use this receipt's credit on one of the client's invoices."""
    receipt = await aget_object_or_404(Receipt, pk=pk)
    invoice = await aget_object_or_404(Invoice, pk=request.POST.get("invoice") or 0, client_id=receipt.client_id)
    form = ApplyCreditForm(request.POST)
    if not await avalidate(form):
        return await error_response(request, form_errors(form))
    applied = await receipts.apply_credit(invoice, request.actor, receipt=receipt, amount=form.cleaned_data["amount"])
    return redirect_with_message(request, reverse("billing:invoice", args=[invoice.pk]),
                                 f"{applied:,.0f} from {receipt.number} applied to {invoice.number}.")


@staff_required(*MONEY)
@require_POST
@service_errors
async def allocation_remove(request, pk):
    """Take back credit applied to the wrong invoice."""
    allocation = await aget_object_or_404(Allocation.objects.select_related("receipt", "invoice"), pk=pk)
    await receipts.remove_allocation(allocation, request.actor)
    return redirect_with_message(request, reverse("billing:invoice", args=[allocation.invoice_id]),
                                 f"Taken back. {allocation.receipt.number}'s {allocation.amount:,.0f} is credit again.")
