from decimal import Decimal

from django.db.models import F, Q, Sum

from apps.billing.models import Invoice, Receipt

from .models import Client


def clients_for(query=""):
    clients = Client.objects.all()
    if query:
        clients = clients.filter(Q(name__icontains=query) | Q(contact_person__icontains=query)
                                 | Q(phone__icontains=query) | Q(email__icontains=query))
    return clients.annotate(
        owing=Sum(F("invoices__total") - F("invoices__amount_paid"), filter=Q(invoices__status__in=Invoice.OPEN))
    )


async def statement(client):
    """Everything billed and paid, oldest first, with a running balance: what the client statement prints."""
    rows = []
    async for inv in Invoice.objects.filter(client=client).exclude(status__in=(Invoice.Status.DRAFT, Invoice.Status.VOID)):
        rows.append({"date": inv.date, "ref": inv.number, "what": "Invoice", "debit": inv.total, "credit": Decimal(0),
                     "url_name": "billing:invoice", "pk": inv.pk})
    async for rct in Receipt.objects.filter(invoice__client=client, status=Receipt.Status.VALID).select_related("invoice"):
        rows.append({"date": rct.date, "ref": rct.number, "what": f"Payment on {rct.invoice.number}", "debit": Decimal(0),
                     "credit": rct.amount, "url_name": "billing:receipt", "pk": rct.pk})
    rows.sort(key=lambda r: (r["date"], r["debit"] == 0))
    balance = Decimal(0)
    for row in rows:
        balance += row["debit"] - row["credit"]
        row["balance"] = balance
    return rows, balance
