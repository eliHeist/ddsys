from django.shortcuts import aget_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.billing import selectors
from apps.billing.forms import SubscriptionForm, lines_for_editor, parse_lines
from apps.billing.models import Invoice, Subscription
from apps.billing.services import subscriptions
from apps.core.http import (arender, avalidate, error_response, form_errors, hx_redirect, paginate, redirect_with_message,
                            service_errors, staff_required, wants_partial)
from apps.core.permissions import MONEY


@staff_required()
async def subscription_list(request):
    status, query = request.GET.get("status", "active"), request.GET.get("q", "").strip()
    page = await paginate(selectors.subscriptions_for(status, query), request)
    template = ("billing/partials/_subscription_rows.html" if wants_partial(request, "subscription-rows")
                else "billing/subscription_list.html")
    return await arender(request, template, {"page_obj": page, "q": query, "status": status})


@staff_required()
async def subscription_detail(request, pk):
    subscription = await selectors.subscription_detail(pk)
    invoices = [i async for i in Invoice.objects.filter(subscription=subscription).order_by("-period_start", "-created_at")]
    return await arender(request, "billing/subscription_detail.html", {"sub": subscription, "invoices": invoices})


async def _editor(request, subscription=None):
    if request.method == "POST":
        form = SubscriptionForm(request.POST)
        if not await avalidate(form):
            return await error_response(request, form_errors(form))
        fields = {**form.cleaned_data, "lines": parse_lines(request.POST)}
        saved = await (subscriptions.update_subscription(subscription, request.actor, **fields) if subscription
                       else subscriptions.create_subscription(request.actor, **fields))
        return hx_redirect(request, reverse("billing:subscription", args=[saved.pk]))
    if subscription:
        initial = {f: getattr(subscription, f) for f in ("title", "interval_months", "start_date", "end_date", "due_days",
                                                         "auto_issue", "external_ref", "notes")}
        initial |= {"client": subscription.client_id, "project": subscription.project_id}
        rows = lines_for_editor([line async for line in subscription.lines.all()])
    else:
        initial = {"client": request.GET.get("client"), "project": request.GET.get("project"),
                   "start_date": timezone.localdate(), "due_days": 7}
        rows = []
    return await arender(request, "billing/subscription_form.html", {
        "form": SubscriptionForm(initial=initial), "rows": rows, "sub": subscription,
        "title": f"Edit {subscription.title}" if subscription else "New subscription",
        "cancel_url": reverse("billing:subscription", args=[subscription.pk]) if subscription else reverse("billing:subscriptions"),
    })


@staff_required(*MONEY)
@service_errors
async def subscription_create(request):
    return await _editor(request)


@staff_required(*MONEY)
@service_errors
async def subscription_edit(request, pk):
    return await _editor(request, await aget_object_or_404(Subscription, pk=pk))


@staff_required(*MONEY)
@require_POST
@service_errors
async def subscription_status(request, pk, status):
    subscription = await aget_object_or_404(Subscription, pk=pk)
    await subscriptions.set_status(subscription, request.actor, status=status)
    labels = {"active": "Subscription resumed.", "paused": "Subscription paused.", "ended": "Subscription ended."}
    return redirect_with_message(request, reverse("billing:subscription", args=[pk]), labels[status])


@staff_required(*MONEY)
@require_POST
@service_errors
async def subscription_invoice_now(request, pk):
    invoice = await subscriptions.invoice_now(await aget_object_or_404(Subscription, pk=pk), request.actor)
    message = f"{invoice.label} made for {invoice.period_start:%d/%m/%Y} to {invoice.period_end:%d/%m/%Y}."
    return redirect_with_message(request, reverse("billing:invoice", args=[invoice.pk]), message)
