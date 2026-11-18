from django.db.models import Q
from django.utils import timezone

from apps.billing import selectors as billing
from apps.billing.models import Invoice, Quotation, Receipt
from apps.clients.models import Client
from apps.finance import selectors as finance
from apps.finance.models import Expense
from apps.projects.models import Project


async def dashboard(can_see_money):
    today = timezone.localdate()
    data = {
        "today": today,
        "outstanding": await billing.outstanding(),
        "overdue": [i async for i in Invoice.objects.filter(status__in=Invoice.OPEN, due_date__lt=today)
                    .select_related("client").order_by("due_date")[:8]],
        "waiting_quotations": [q async for q in Quotation.objects.filter(status=Quotation.Status.ISSUED)
                               .select_related("client").order_by("valid_until")[:8]],
        "drafts": [d async for d in Invoice.objects.filter(status=Invoice.Status.DRAFT).select_related("client")[:8]],
        "projects": [p async for p in Project.objects.filter(status=Project.Status.ACTIVE)
                     .select_related("client").order_by("due_date")[:8]],
    }
    if can_see_money:
        data |= {
            "accounts": await finance.balances(),
            "month": await finance.month_totals(today.year, today.month),
            "receipts": [r async for r in Receipt.objects.select_related("invoice", "quotation", "project", "account")[:6]],
            "expenses": [e async for e in Expense.objects.select_related("category", "account", "loan")[:6]],
        }
    return data


async def search(query, limit=6):
    """A few hits of each kind for the search box in the header."""
    if len(query) < 2:
        return []
    groups = [
        ("Clients", "clients:detail", [c async for c in Client.objects.filter(
            Q(name__icontains=query) | Q(contact_person__icontains=query) | Q(phone__icontains=query))[:limit]],
         lambda c: (c.name, c.contact_person)),
        ("Projects", "projects:detail", [p async for p in Project.objects.select_related("client").filter(
            Q(title__icontains=query) | Q(client__name__icontains=query))[:limit]], lambda p: (p.title, p.client.name if p.client else "Dakdot's own work")),
        ("Invoices", "billing:invoice", [i async for i in Invoice.objects.select_related("client").filter(
            Q(number__icontains=query) | Q(client__name__icontains=query))[:limit]],
         lambda i: (i.label, f"{i.client.name} · {i.get_status_display()}")),
        ("Quotations", "billing:quotation", [q async for q in Quotation.objects.select_related("client").filter(
            Q(number__icontains=query) | Q(client__name__icontains=query))[:limit]],
         lambda q: (q.label, f"{q.client.name} · {q.get_status_display()}")),
        ("Receipts", "billing:receipt", [r async for r in Receipt.objects.filter(
            Q(number__icontains=query) | Q(reference__icontains=query) | Q(received_from__icontains=query))[:limit]],
         lambda r: (r.number, f"{r.received_from} · {r.amount:,.0f}")),
    ]
    return [{"title": title, "url_name": url_name, "items": [(o.pk, *describe(o)) for o in objs]}
            for title, url_name, objs, describe in groups if objs]
