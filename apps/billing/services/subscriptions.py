"""Subscriptions: a client billed every period for a product plan or a service (hosting, a retainer).

`bill_due_subscriptions` runs every day (manage.py bill_subscriptions, from cron or the server's scheduler) and
makes the invoices that have fallen due; staff can also invoice one straight away from its page.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.billing.models import Invoice, InvoiceLine, Subscription, SubscriptionLine
from apps.core.async_utils import service
from apps.core.dates import add_months, period_end
from apps.core.models import CompanySettings
from apps.core.permissions import MONEY, require_role

from .common import assert_project_matches, copy_lines, days_from, write_lines
from .invoices import issue

Status = Subscription.Status
MAX_CATCH_UP = 12  # periods billed in one run for a subscription that fell far behind


def _lock(subscription):
    return Subscription.objects.select_for_update().select_related("client").get(pk=subscription.pk)


def _check(client, project, start_date, end_date):
    assert_project_matches(client, project)
    if project is not None and project.is_internal:
        raise ValidationError("Internal projects don't take subscriptions. Link a product or a client project.")
    if end_date and end_date < start_date:
        raise ValidationError("The end date is before the start date.")


@service
@transaction.atomic
def create_subscription(by, *, client, title, lines, start_date, interval_months, project=None, end_date=None,
                        auto_issue=False, due_days=7, external_ref="", notes=""):
    """Start billing a client. The first invoice is made on `start_date`."""
    require_role(by, *MONEY)
    _check(client, project, start_date, end_date)
    subscription = Subscription.objects.create(
        client=client, project=project, title=title.strip(), start_date=start_date, next_invoice_date=start_date,
        interval_months=interval_months, end_date=end_date, auto_issue=auto_issue, due_days=due_days,
        external_ref=external_ref.strip(), notes=notes, created_by=by,
    )
    write_lines(subscription, SubscriptionLine, "subscription", lines)
    return subscription


@service
@transaction.atomic
def update_subscription(subscription, by, *, client, title, lines, start_date, interval_months, project=None,
                        end_date=None, auto_issue=False, due_days=7, external_ref="", notes=""):
    """Change the plan. Invoices already made keep their lines; the next one uses the new ones.
    The start date only moves the next invoice date while nothing has been invoiced yet."""
    require_role(by, *MONEY)
    subscription = _lock(subscription)
    if subscription.status == Status.ENDED:
        raise ValidationError("This subscription has ended. Start a new one instead.")
    _check(client, project, start_date, end_date)
    has_invoices = subscription.invoices.exists()
    if has_invoices and client.pk != subscription.client_id:
        raise ValidationError("This subscription has invoices, so its client cannot change.")
    if not has_invoices:
        subscription.start_date = subscription.next_invoice_date = start_date
    subscription.client, subscription.project, subscription.title = client, project, title.strip()
    subscription.interval_months, subscription.end_date, subscription.auto_issue = interval_months, end_date, auto_issue
    subscription.due_days, subscription.external_ref, subscription.notes = due_days, external_ref.strip(), notes
    subscription.save()
    write_lines(subscription, SubscriptionLine, "subscription", lines)
    return subscription


@service
@transaction.atomic
def set_status(subscription, by, *, status):
    """Pause (no invoices until resumed), resume, or end for good."""
    require_role(by, *MONEY)
    subscription = _lock(subscription)
    if subscription.status == Status.ENDED:
        raise ValidationError("This subscription has ended and cannot change.")
    if status not in Status.values or status == subscription.status:
        raise ValidationError("Nothing to change.")
    if status == Status.ACTIVE and subscription.next_invoice_date < timezone.localdate():
        # resuming after a pause: start again from today rather than billing the paused months
        subscription.next_invoice_date = timezone.localdate()
    subscription.status = status
    subscription.save(update_fields=["status", "next_invoice_date", "updated_at"])
    return subscription


def make_invoice(subscription):
    """The invoice for the subscription's next period (locked row expected), then move the next date on.
    Issued straight away when `auto_issue` is on; otherwise left as a draft to check and issue."""
    if subscription.status != Status.ACTIVE:
        raise ValidationError(f"The subscription is {subscription.get_status_display().lower()}.")
    start = subscription.next_invoice_date
    end = period_end(start, subscription.interval_months)
    if subscription.end_date and start > subscription.end_date:
        raise ValidationError("The subscription's end date has passed.")
    if not subscription.lines.exists():
        raise ValidationError("The subscription has no lines to invoice.")
    notes = f"{subscription.title}: {start:%d/%m/%Y} to {end:%d/%m/%Y}."
    invoice = Invoice.objects.create(
        client=subscription.client, project=subscription.project, subscription=subscription, period_start=start,
        period_end=end, currency=subscription.currency, notes=f"{notes}\n{subscription.notes}".strip(),
        terms=CompanySettings.load().invoice_terms, created_by=subscription.created_by,
    )
    copy_lines(subscription, InvoiceLine, "invoice", invoice)
    if subscription.auto_issue:
        issue(invoice)
        invoice.due_date = days_from(invoice.date, subscription.due_days)
        invoice.save(update_fields=["due_date", "updated_at"])
    subscription.next_invoice_date = add_months(start, subscription.interval_months)
    if subscription.end_date and subscription.next_invoice_date > subscription.end_date:
        subscription.status = Status.ENDED
    subscription.save(update_fields=["next_invoice_date", "status", "updated_at"])
    return invoice


@service
@transaction.atomic
def invoice_now(subscription, by):
    """Make the next period's invoice today instead of waiting for its date."""
    require_role(by, *MONEY)
    return make_invoice(_lock(subscription))


def bill_due_subscriptions(on_date=None):
    """Invoice every active subscription whose next date has come, catching up missed periods. One transaction per
    subscription, so one bad subscription doesn't stop the rest. Returns (invoices made, errors)."""
    on_date = on_date or timezone.localdate()
    made, errors = [], []
    due = Subscription.objects.filter(status=Status.ACTIVE, next_invoice_date__lte=on_date).values_list("pk", flat=True)
    for pk in list(due):
        for _ in range(MAX_CATCH_UP):
            try:
                with transaction.atomic():
                    subscription = Subscription.objects.select_for_update().select_related("client").get(pk=pk)
                    if subscription.status != Status.ACTIVE or subscription.next_invoice_date > on_date:
                        break
                    made.append(make_invoice(subscription))
            except ValidationError as error:
                errors.append((pk, "; ".join(error.messages)))
                break
    return made, errors

