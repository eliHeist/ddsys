from decimal import Decimal

from django.db.models import F, Prefetch, Q, Sum

from .models import Invoice, Quotation, Receipt

INVOICE_FILTERS = {"open": Invoice.OPEN, "paid": (Invoice.Status.PAID,), "draft": (Invoice.Status.DRAFT,),
                   "void": (Invoice.Status.VOID,)}
QUOTATION_FILTERS = {"open": (Quotation.Status.ISSUED,), "accepted": (Quotation.Status.ACCEPTED,),
                     "declined": (Quotation.Status.DECLINED,), "draft": (Quotation.Status.DRAFT,),
                     "void": (Quotation.Status.VOID,)}


def _search(documents, query):
    if query:
        documents = documents.filter(Q(number__icontains=query) | Q(client__name__icontains=query)
                                     | Q(project__title__icontains=query) | Q(lines__description__icontains=query)).distinct()
    return documents


def invoices_for(status="", query="", client_id=""):
    invoices = Invoice.objects.select_related("client", "project")
    if status in INVOICE_FILTERS:
        invoices = invoices.filter(status__in=INVOICE_FILTERS[status])
    if status == "overdue":
        from django.utils import timezone
        invoices = invoices.filter(status__in=Invoice.OPEN, due_date__lt=timezone.localdate())
    if client_id:
        invoices = invoices.filter(client_id=client_id)
    return _search(invoices, query)


def quotations_for(status="", query=""):
    quotations = Quotation.objects.select_related("client", "project")
    if status in QUOTATION_FILTERS:
        quotations = quotations.filter(status__in=QUOTATION_FILTERS[status])
    return _search(quotations, query)


def receipts_for(query="", account_id=""):
    receipts = Receipt.objects.select_related("invoice__client", "account")
    if account_id:
        receipts = receipts.filter(account_id=account_id)
    if query:
        receipts = receipts.filter(Q(number__icontains=query) | Q(invoice__number__icontains=query)
                                   | Q(received_from__icontains=query) | Q(reference__icontains=query))
    return receipts


async def outstanding():
    total = await Invoice.objects.filter(status__in=Invoice.OPEN).aaggregate(owing=Sum(F("total") - F("amount_paid")))
    return total["owing"] or Decimal(0)


async def invoice_detail(pk):
    return await Invoice.objects.select_related("client", "project", "quotation", "created_by").prefetch_related(
        "lines", Prefetch("receipts", queryset=Receipt.objects.select_related("account"))).aget(pk=pk)


async def quotation_detail(pk):
    return await Quotation.objects.select_related("client", "project", "created_by").prefetch_related(
        "lines", "invoices").aget(pk=pk)


async def receipt_detail(pk):
    return await Receipt.objects.select_related("invoice__client", "account", "received_by").aget(pk=pk)
