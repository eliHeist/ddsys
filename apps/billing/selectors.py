from decimal import Decimal

from django.db.models import DecimalField, F, Max, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce

from .models import Allocation, Invoice, Quotation, Receipt, Subscription

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
    receipts = Receipt.objects.select_related("client", "invoice", "quotation", "project", "account")
    if account_id:
        receipts = receipts.filter(account_id=account_id)
    if query:
        receipts = receipts.filter(Q(number__icontains=query) | Q(invoice__number__icontains=query)
                                   | Q(received_from__icontains=query) | Q(reference__icontains=query)
                                   | Q(client__name__icontains=query) | Q(quotation__number__icontains=query))
    return receipts


def with_credit(receipts):
    """Annotate `credit`: what each receipt has not yet paid towards an invoice."""
    used = Coalesce(Sum("allocations__amount"), Value(0), output_field=DecimalField(max_digits=14, decimal_places=2))
    return receipts.annotate(credit=F("amount") - used)


async def credit_receipts(client_id, **filters):
    """A client's valid receipts with credit left, oldest first (deposits and overpayments)."""
    receipts = with_credit(Receipt.objects.filter(client_id=client_id, status=Receipt.Status.VALID, **filters)
                           .select_related("quotation", "project", "invoice")).filter(credit__gt=0).order_by("date", "id")
    return [r async for r in receipts]


async def client_credit(client_id):
    """The client's money not yet used on an invoice."""
    paid = (await Receipt.objects.filter(client_id=client_id, status=Receipt.Status.VALID)
            .aaggregate(s=Sum("amount")))["s"] or Decimal(0)
    used = (await Allocation.objects.filter(receipt__client_id=client_id, receipt__status=Receipt.Status.VALID)
            .aaggregate(s=Sum("amount")))["s"] or Decimal(0)
    return paid - used


async def outstanding():
    total = await Invoice.objects.filter(status__in=Invoice.OPEN).aaggregate(owing=Sum(F("total") - F("amount_paid")))
    return total["owing"] or Decimal(0)


async def invoice_detail(pk):
    return await Invoice.objects.select_related("client", "project", "quotation", "subscription", "created_by").prefetch_related(
        "lines", Prefetch("allocations", queryset=Allocation.objects.select_related("receipt__account")
                          .filter(receipt__status=Receipt.Status.VALID))).aget(pk=pk)


async def quotation_detail(pk):
    return await Quotation.objects.select_related("client", "project", "created_by").prefetch_related(
        "lines", "invoices").aget(pk=pk)


async def receipt_detail(pk):
    return await with_credit(Receipt.objects.select_related("client", "invoice", "quotation", "project", "account",
                                                            "received_by")).prefetch_related(
        Prefetch("allocations", queryset=Allocation.objects.select_related("invoice"))).aget(pk=pk)


SUBSCRIPTION_FILTERS = {"active": (Subscription.Status.ACTIVE,), "paused": (Subscription.Status.PAUSED,),
                        "ended": (Subscription.Status.ENDED,)}


def subscriptions_for(status="", query="", project_id=""):
    subscriptions = (Subscription.objects.select_related("client", "project").prefetch_related("lines")
                     .annotate(paid_through=Max("invoices__period_end", filter=Q(invoices__status=Invoice.Status.PAID))))
    if status in SUBSCRIPTION_FILTERS:
        subscriptions = subscriptions.filter(status__in=SUBSCRIPTION_FILTERS[status])
    if project_id:
        subscriptions = subscriptions.filter(project_id=project_id)
    if query:
        subscriptions = subscriptions.filter(Q(title__icontains=query) | Q(client__name__icontains=query)
                                             | Q(external_ref__icontains=query) | Q(project__title__icontains=query))
    return subscriptions


async def subscription_detail(pk):
    return await subscriptions_for().select_related("created_by").aget(pk=pk)


async def product_subscriptions(project):
    """A product's subscribers, with the monthly value of the active ones."""
    rows = [s async for s in subscriptions_for(project_id=project.pk)]
    active = [s for s in rows if s.status == Subscription.Status.ACTIVE]
    return {"subscriptions": rows, "active_count": len(active),
            "monthly": sum((s.monthly_value for s in active), Decimal(0))}
