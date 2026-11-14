from decimal import Decimal

from django.db.models import Q, Sum

from apps.billing.models import Invoice, Quotation, Receipt
from apps.finance.models import Expense

from .models import Project

FILTERS = {"open": (Project.Status.LEAD, Project.Status.ACTIVE, Project.Status.ON_HOLD),
           "completed": (Project.Status.COMPLETED,), "cancelled": (Project.Status.CANCELLED,)}


def projects_for(status="", query=""):
    projects = Project.objects.select_related("client", "lead")
    if status in FILTERS:
        projects = projects.filter(status__in=FILTERS[status])
    if query:
        projects = projects.filter(Q(title__icontains=query) | Q(client__name__icontains=query))
    return projects


async def money_summary(project):
    """Invoiced, received, spent and the profit so far. Drafts and voided documents don't count."""
    live = Invoice.objects.filter(project=project).exclude(status__in=(Invoice.Status.DRAFT, Invoice.Status.VOID))
    invoiced = (await live.aaggregate(s=Sum("total")))["s"] or Decimal(0)
    received = (await Receipt.objects.filter(invoice__project=project, status=Receipt.Status.VALID)
                .aaggregate(s=Sum("amount")))["s"] or Decimal(0)
    spent = (await Expense.objects.filter(project=project, status=Expense.Status.VALID)
             .aaggregate(s=Sum("amount")))["s"] or Decimal(0)
    return {"invoiced": invoiced, "received": received, "owing": invoiced - received, "spent": spent,
            "profit": invoiced - spent, "cash_profit": received - spent}


async def documents(project):
    return {
        "quotations": [q async for q in Quotation.objects.filter(project=project)],
        "invoices": [i async for i in Invoice.objects.filter(project=project)],
        "expenses": [e async for e in Expense.objects.filter(project=project).select_related("category", "account")],
    }
