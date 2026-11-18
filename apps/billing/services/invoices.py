from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.billing.models import Invoice, InvoiceLine
from apps.core.async_utils import service
from apps.core.models import CompanySettings
from apps.core.permissions import EVERYONE, MONEY, require_role

from .common import assert_draft, assert_project_matches, days_from, replace_lines, today
from .receipts import auto_apply, release

Status = Invoice.Status


def _lock(invoice):
    return Invoice.objects.select_for_update().get(pk=invoice.pk)


@service
@transaction.atomic
def create_invoice(by, *, client, lines, project=None, notes="", terms=None, due_date=None):
    """Save a new draft invoice. Anyone may draft; issuing needs a finance role."""
    require_role(by, *EVERYONE)
    assert_project_matches(client, project)
    invoice = Invoice.objects.create(
        client=client, project=project, notes=notes, due_date=due_date, created_by=by,
        terms=CompanySettings.load().invoice_terms if terms is None else terms,
    )
    replace_lines(invoice, InvoiceLine, "invoice", lines)
    return invoice


@service
@transaction.atomic
def update_invoice(invoice, by, *, client, lines, project=None, notes="", terms="", due_date=None):
    require_role(by, *EVERYONE)
    invoice = _lock(invoice)
    assert_draft(invoice)
    assert_project_matches(client, project)
    if invoice.quotation_id and client.pk != invoice.client_id:
        raise ValidationError("This invoice comes from a quotation, so its client cannot change.")
    invoice.client, invoice.project, invoice.notes, invoice.terms, invoice.due_date = client, project, notes, terms, due_date
    invoice.save()
    replace_lines(invoice, InvoiceLine, "invoice", lines)
    return invoice


def issue(invoice, by=None):
    """Date a locked draft today, number it and freeze it, then apply any deposit made for its quotation or project.
    No permission check: for services that already did one (issue_invoice) or that run unattended (subscriptions)."""
    assert_draft(invoice)
    if not invoice.lines.exists() or invoice.total <= 0:
        raise ValidationError("An invoice needs at least one line and a total above 0.")
    invoice.date = today()
    if invoice.due_date is None or invoice.due_date < invoice.date:
        invoice.due_date = days_from(invoice.date, CompanySettings.load().invoice_due_days)
    invoice.status, invoice.issued_at = Status.ISSUED, timezone.now()
    invoice.save()
    auto_apply(invoice, by)
    return invoice


@service
@transaction.atomic
def issue_invoice(invoice, by):
    """Date it today, give it its number (INV + today) and freeze it. From now on it can be paid."""
    require_role(by, *MONEY)
    return issue(_lock(invoice), by)


@service
@transaction.atomic
def void_invoice(invoice, by, *, reason):
    """Cancel an issued invoice. Its number stays used. Whatever was paid towards it is not lost: it goes back to
    the client as credit, ready for the invoice that replaces it."""
    require_role(by, *MONEY)
    invoice = _lock(invoice)
    if invoice.is_draft:
        raise ValidationError("Delete a draft instead of voiding it.")
    if invoice.is_void:
        raise ValidationError(f"{invoice.label} is already void.")
    if not (reason or "").strip():
        raise ValidationError("Say why it is being voided.")
    release(invoice)
    invoice.status, invoice.voided_at, invoice.void_reason = Status.VOID, timezone.now(), reason.strip()
    invoice.amount_paid = 0
    invoice.save(update_fields=["status", "voided_at", "void_reason", "amount_paid", "updated_at"])
    return invoice


@service
@transaction.atomic
def delete_draft(invoice, by):
    require_role(by, *EVERYONE)
    invoice = _lock(invoice)
    assert_draft(invoice)
    invoice.delete()
