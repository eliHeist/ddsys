from datetime import datetime

from asgiref.sync import sync_to_async
from django.http import HttpResponse
from django.shortcuts import aget_object_or_404
from ninja import Router
from ninja.pagination import paginate

from apps.documents import layouts

from .. import selectors
from ..schemas import ReceiptOut

router = Router(tags=["Receipts"])


@router.get("/receipts", response=list[ReceiptOut], summary="Payments on the product's invoices, and deposits for it")
@paginate
async def list_receipts(request, invoice_id: int | None = None, updated_since: datetime | None = None):
    """Filter by `invoice_id` or `updated_since`. Voided receipts are included with `status: void`.
    A deposit (paid before its invoice) has no `invoice_id`; `credit` is the part not yet used on an invoice."""
    qs = selectors.receipts(request.auth.product)
    if invoice_id:
        qs = qs.filter(invoice_id=invoice_id)
    if updated_since:
        qs = qs.filter(updated_at__gte=updated_since)
    return qs


@router.get("/receipts/{receipt_id}/pdf", url_name="receipt_pdf", summary="The receipt as a PDF",
            openapi_extra={"responses": {200: {"content": {"application/pdf": {}}}}})
async def receipt_pdf(request, receipt_id: int):
    receipt = await aget_object_or_404(selectors.receipts(request.auth.product).select_related("account"), pk=receipt_id)
    data = await sync_to_async(layouts.receipt)(receipt)
    response = HttpResponse(data, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{receipt.number}.pdf"'
    return response
