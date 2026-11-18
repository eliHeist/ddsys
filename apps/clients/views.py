from django.shortcuts import aget_object_or_404
from django.urls import reverse

from apps.billing import selectors as billing
from apps.billing.forms import deposit_dialog
from apps.billing.models import Invoice, Quotation
from apps.core.http import arender, form_page, paginate, staff_required, wants_partial
from apps.finance.models import Account
from apps.core.permissions import MONEY
from apps.projects.models import Project

from . import selectors
from .forms import ClientForm
from .models import Client


@staff_required()
async def client_list(request):
    query = request.GET.get("q", "").strip()
    page = await paginate(selectors.clients_for(query), request)
    template = "clients/partials/_client_rows.html" if wants_partial(request, "client-rows") else "clients/client_list.html"
    return await arender(request, template, {"page_obj": page, "q": query})


@staff_required()
async def client_detail(request, pk):
    client = await aget_object_or_404(Client, pk=pk)
    rows, balance = await selectors.statement(client)
    projects = [p async for p in Project.objects.filter(client=client)]
    quotations = [q async for q in Quotation.objects.filter(client=client)[:20]]
    credit_receipts = await billing.credit_receipts(client.pk)
    context = {
        "client": client, "projects": projects, "quotations": quotations,
        "invoices": [i async for i in Invoice.objects.filter(client=client)[:20]],
        "statement": rows, "owing": await selectors.owing(client), "credit_receipts": credit_receipts,
        "credit": sum((r.credit for r in credit_receipts), 0),
    }
    if request.actor.is_superuser or request.staff.role in MONEY:
        accounts = [a async for a in Account.objects.filter(is_active=True)]
        depositable = [q for q in quotations if q.status in (Quotation.Status.ISSUED, Quotation.Status.ACCEPTED)]
        context["deposit_dialog"] = deposit_dialog(client, accounts, quotations=depositable, projects=projects)
    return await arender(request, "clients/client_detail.html", context)


@staff_required()
async def client_create(request):
    return await form_page(request, form_class=ClientForm, title="New client", cancel_url=reverse("clients:list"),
                           success_url=lambda c: reverse("clients:detail", args=[c.pk]))


@staff_required()
async def client_edit(request, pk):
    client = await aget_object_or_404(Client, pk=pk)
    return await form_page(request, form_class=ClientForm, instance=client, title=f"Edit {client.name}",
                           cancel_url=reverse("clients:detail", args=[pk]), success_url=reverse("clients:detail", args=[pk]))


@staff_required()
async def client_statement(request, pk):
    client = await aget_object_or_404(Client, pk=pk)
    rows, balance = await selectors.statement(client)
    return await arender(request, "clients/client_statement.html", {"client": client, "statement": rows, "balance": balance})
