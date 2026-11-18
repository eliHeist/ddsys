from datetime import datetime

from asgiref.sync import sync_to_async
from django.http import HttpResponse
from django.shortcuts import aget_object_or_404
from ninja import Router
from ninja.pagination import paginate

from apps.documents import layouts

from .. import selectors
from ..schemas import InvoiceDetailOut, InvoiceOut

router = Router(tags=["Invoices"])


@router.get("/invoices", response=list[InvoiceOut], summary="The product's invoices (no drafts)")
@paginate
async def list_invoices(request, status: str | None = None, client_id: int | None = None,
                        subscription_id: int | None = None, updated_since: datetime | None = None):
    """Filter by `status` (issued / partial / paid / void), `client_id`, `subscription_id` or `updated_since`."""
    qs = selectors.invoices(request.auth.product)
    if status:
        qs = qs.filter(status=status)
    if client_id:
        qs = qs.filter(client_id=client_id)
    if subscription_id:
        qs = qs.filter(subscription_id=subscription_id)
    if updated_since:
        qs = qs.filter(updated_at__gte=updated_since)
    return qs


@router.get("/invoices/{invoice_id}", response=InvoiceDetailOut, summary="One invoice with its lines and payments")
async def get_invoice(request, invoice_id: int):
    return await aget_object_or_404(selectors.invoice_detail(request.auth.product), pk=invoice_id)


@router.get("/invoices/{invoice_id}/pdf", url_name="invoice_pdf", summary="The invoice as a PDF",
            openapi_extra={"responses": {200: {"content": {"application/pdf": {}}}}})
async def invoice_pdf(request, invoice_id: int):
    invoice = await aget_object_or_404(selectors.invoice_detail(request.auth.product), pk=invoice_id)
    data = await sync_to_async(layouts.billing_document)(invoice)
    response = HttpResponse(data, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{invoice.number}.pdf"'
    return response
