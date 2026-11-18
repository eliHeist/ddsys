from decimal import Decimal

from django.db.models import F, Q, Sum

from apps.billing.models import Invoice, Quotation, Receipt
from apps.finance.models import Expense, Transaction

from .models import Project

FILTERS = {"open": (Project.Status.LEAD, Project.Status.ACTIVE, Project.Status.ON_HOLD),
           "completed": (Project.Status.COMPLETED,), "cancelled": (Project.Status.CANCELLED,)}


def projects_for(status="", query="", kinds=(Project.Kind.CLIENT, Project.Kind.INTERNAL)):
    """Projects of the given kinds (the Projects page: client work and internal; the Products page: products)."""
    projects = Project.objects.select_related("client", "lead").filter(kind__in=kinds)
    if status in FILTERS:
        projects = projects.filter(status__in=FILTERS[status])
    if query:
        projects = projects.filter(Q(title__icontains=query) | Q(client__name__icontains=query))
    return projects


async def money_summary(project):
    """Invoiced, received, spent and the profit so far. Drafts and voided documents don't count."""
    live = Invoice.objects.filter(project=project).exclude(status__in=(Invoice.Status.DRAFT, Invoice.Status.VOID))
    invoiced = (await live.aaggregate(s=Sum("total")))["s"] or Decimal(0)
    received = (await Receipt.objects.filter(Q(project=project) | Q(invoice__project=project), status=Receipt.Status.VALID)
                .aaggregate(s=Sum("amount")))["s"] or Decimal(0)  # deposits for it count as soon as they arrive
    owing = (await live.aaggregate(s=Sum(F("total") - F("amount_paid"))))["s"] or Decimal(0)
    spent = (await Expense.objects.filter(project=project, status=Expense.Status.VALID)
             .aaggregate(s=Sum(F("amount") + F("fee"))))["s"] or Decimal(0)
    other = (await Transaction.objects.filter(project=project, kind=Transaction.Kind.OTHER_INCOME, is_void=False)
             .aaggregate(s=Sum("amount")))["s"] or Decimal(0)
    income = invoiced + other
    return {"invoiced": invoiced, "received": received + other, "other_income": other, "owing": owing,
            "income": income, "spent": spent, "profit": income - spent}


async def documents(project):
    return {
        "quotations": [q async for q in Quotation.objects.filter(project=project)],
        "invoices": [i async for i in Invoice.objects.filter(project=project)],
        "expenses": [e async for e in Expense.objects.filter(project=project).select_related("category", "account", "loan")],
        "other_income": [t async for t in Transaction.objects.filter(project=project, kind=Transaction.Kind.OTHER_INCOME)
                         .select_related("account")],
    }


async def secrets(project):
    """The project's variables and logins, without their values (those are fetched one at a time when needed)."""
    rows = [s async for s in project.secrets.defer("encrypted_value")]
    return {"variables": [s for s in rows if not s.is_login], "logins": [s for s in rows if s.is_login],
            "secret_count": len(rows)}
