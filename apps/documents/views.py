from asgiref.sync import sync_to_async
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.utils.http import content_disposition_header

from apps.billing.models import Invoice, Quotation, Receipt
from apps.clients import selectors as client_selectors
from apps.clients.models import Client
from apps.core.http import staff_required

from . import layouts


def _billing(model):
    def build(pk):
        doc = model.objects.select_related("client").prefetch_related("lines").get(pk=pk)
        if doc.is_draft:
            raise Http404("Drafts have no PDF: issue the document first.")
        return doc.number, layouts.billing_document(doc)
    return build


def _receipt(pk):
    rct = Receipt.objects.select_related("invoice", "quotation", "project", "account").get(pk=pk)
    return rct.number, layouts.receipt(rct)


BUILDERS = {"invoice": _billing(Invoice), "quotation": _billing(Quotation), "receipt": _receipt}


@staff_required()
async def pdf(request, kind, pk):
    """The PDF as a download named after the document: INV261850011.pdf."""
    try:
        if kind == "statement":
            client = await Client.objects.aget(pk=pk)
            rows, balance = await client_selectors.statement(client)
            name = f"Statement {client.name} {timezone.localdate():%Y-%m-%d}"
            data = await sync_to_async(layouts.statement)(client, rows, balance)
        elif kind in BUILDERS:
            name, data = await sync_to_async(BUILDERS[kind])(pk)
        else:
            raise Http404
    except (Invoice.DoesNotExist, Quotation.DoesNotExist, Receipt.DoesNotExist, Client.DoesNotExist):
        raise Http404
    response = HttpResponse(data, content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=f"{name}.pdf")
    return response
