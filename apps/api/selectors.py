"""Querysets the API serves, always limited to the calling key's product. Everything the schemas read is
select_related / prefetch_related here, because schemas are filled in after the async query has run."""

from django.db.models import Count, F, Max, Prefetch, Q, Sum
from django.utils import timezone

from apps.billing.models import Allocation, Invoice, Receipt, Subscription
from apps.billing.selectors import with_credit


def subscriptions(product):
    today = timezone.localdate()
    is_open = Q(invoices__status__in=Invoice.OPEN)
    return (Subscription.objects.filter(project=product).select_related("client").prefetch_related("lines")
            .annotate(paid_through=Max("invoices__period_end", filter=Q(invoices__status=Invoice.Status.PAID)),
                      owing=Sum(F("invoices__total") - F("invoices__amount_paid"), filter=is_open),
                      overdue_invoices=Count("invoices", filter=is_open & Q(invoices__due_date__lt=today)))
            .order_by("id"))


def invoices(product):
    """Issued, paid and void invoices; drafts are Dakdot's work in progress and are never shown."""
    return (Invoice.objects.filter(project=product).exclude(status=Invoice.Status.DRAFT)
            .select_related("client").order_by("id"))


def invoice_detail(product):
    return invoices(product).prefetch_related(
        "lines", Prefetch("allocations", queryset=Allocation.objects.filter(receipt__status="valid")),
        Prefetch("allocations__receipt", queryset=with_credit(Receipt.objects.select_related("invoice"))))


def receipts(product):
    """Payments on the product's invoices and deposits made for it."""
    return with_credit(Receipt.objects.filter(Q(invoice__project=product) | Q(project=product))
                       .select_related("invoice")).order_by("id")
