from asgiref.sync import sync_to_async
from django.http import Http404, HttpResponse

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
    rct = Receipt.objects.select_related("invoice", "account").get(pk=pk)
    return rct.number, layouts.receipt(rct)


BUILDERS = {"invoice": _billing(Invoice), "quotation": _billing(Quotation), "receipt": _receipt}


@staff_required()
async def pdf(request, kind, pk):
    """The PDF, shown in the browser tab (Content-Disposition inline) so it can be printed or saved."""
    try:
        if kind == "statement":
            client = await Client.objects.aget(pk=pk)
            rows, balance = await client_selectors.statement(client)
            name, data = f"Statement {client.name}", await sync_to_async(layouts.statement)(client, rows, balance)
        elif kind in BUILDERS:
            name, data = await sync_to_async(BUILDERS[kind])(pk)
        else:
            raise Http404
    except (Invoice.DoesNotExist, Quotation.DoesNotExist, Receipt.DoesNotExist, Client.DoesNotExist):
        raise Http404
    response = HttpResponse(data, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{name}.pdf"'
    return response
