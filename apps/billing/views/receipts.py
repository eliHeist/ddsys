from django.shortcuts import aget_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.billing import selectors
from apps.billing.forms import void_dialog
from apps.billing.models import Receipt
from apps.billing.services import receipts
from apps.core.http import arender, redirect_with_message, paginate, service_errors, staff_required, wants_partial
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
    return await arender(request, "billing/receipt_detail.html", {
        "receipt": receipt,
        "void_dialog": void_dialog(f"Void {receipt.number}", reverse("billing:receipt-void", args=[pk]),
                                   "The receipt") | {"message": "The money comes out of the account again and the invoice owes it again. The receipt keeps its number, marked void."},
    })


@staff_required(*MONEY)
@require_POST
@service_errors
async def receipt_void(request, pk):
    receipt = await aget_object_or_404(Receipt, pk=pk)
    await receipts.void_receipt(receipt, request.actor, reason=request.POST.get("reason", ""))
    return redirect_with_message(request, reverse("billing:receipt", args=[pk]), "Receipt voided.")
