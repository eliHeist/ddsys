from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.billing.models import Invoice, InvoiceLine, Quotation, QuotationLine
from apps.core.async_utils import service
from apps.core.models import CompanySettings
from apps.core.permissions import EVERYONE, require_role

from .common import assert_draft, assert_project_matches, copy_lines, days_from, replace_lines, today

Status = Quotation.Status


def _lock(quotation):
    return Quotation.objects.select_for_update().get(pk=quotation.pk)


@service
@transaction.atomic
def create_quotation(by, *, client, lines, project=None, notes="", terms=None, valid_until=None):
    """Save a new draft quotation."""
    require_role(by, *EVERYONE)
    assert_project_matches(client, project)
    quotation = Quotation.objects.create(
        client=client, project=project, notes=notes, valid_until=valid_until, created_by=by,
        terms=CompanySettings.load().quotation_terms if terms is None else terms,
    )
    replace_lines(quotation, QuotationLine, "quotation", lines)
    return quotation


@service
@transaction.atomic
def update_quotation(quotation, by, *, client, lines, project=None, notes="", terms="", valid_until=None):
    """Change a draft: its client, project, lines, notes and terms."""
    require_role(by, *EVERYONE)
    quotation = _lock(quotation)
    assert_draft(quotation)
    assert_project_matches(client, project)
    quotation.client, quotation.project, quotation.notes = client, project, notes
    quotation.terms, quotation.valid_until = terms, valid_until
    quotation.save()
    replace_lines(quotation, QuotationLine, "quotation", lines)
    return quotation


@service
@transaction.atomic
def issue_quotation(quotation, by):
    """Date it today, give it its number and freeze it, ready to send."""
    require_role(by, *EVERYONE)
    quotation = _lock(quotation)
    assert_draft(quotation)
    if not quotation.lines.exists():
        raise ValidationError("Add at least one line before issuing.")
    quotation.date = today()
    if quotation.valid_until is None or quotation.valid_until < quotation.date:
        quotation.valid_until = days_from(quotation.date, CompanySettings.load().quotation_valid_days)
    quotation.status, quotation.issued_at = Status.ISSUED, timezone.now()
    quotation.save()
    return quotation


@service
@transaction.atomic
def decide_quotation(quotation, by, *, accepted):
    """Record the client's answer to an issued quotation."""
    require_role(by, *EVERYONE)
    quotation = _lock(quotation)
    if quotation.status != Status.ISSUED:
        raise ValidationError(f"{quotation.label} is {quotation.get_status_display().lower()}: only issued quotations can be accepted or declined.")
    quotation.status = Status.ACCEPTED if accepted else Status.DECLINED
    quotation.decided_at = timezone.now()
    quotation.save(update_fields=["status", "decided_at", "updated_at"])
    return quotation


@service
@transaction.atomic
def convert_to_invoice(quotation, by):
    """Copy an issued or accepted quotation's lines into a new draft invoice. Accepts the quotation if needed."""
    require_role(by, *EVERYONE)
    quotation = _lock(quotation)
    if quotation.status not in (Status.ISSUED, Status.ACCEPTED):
        raise ValidationError("Only an issued or accepted quotation can become an invoice.")
    if quotation.invoices.exclude(status=Invoice.Status.VOID).exists():
        raise ValidationError(f"{quotation.label} already has an invoice. Void that invoice first to make a new one.")
    if quotation.status == Status.ISSUED:
        quotation.status, quotation.decided_at = Status.ACCEPTED, timezone.now()
        quotation.save(update_fields=["status", "decided_at", "updated_at"])
    settings = CompanySettings.load()
    invoice = Invoice.objects.create(
        client=quotation.client, project=quotation.project, quotation=quotation, notes=quotation.notes,
        terms=settings.invoice_terms, created_by=by,
    )
    copy_lines(quotation, InvoiceLine, "invoice", invoice)
    return invoice


@service
@transaction.atomic
def void_quotation(quotation, by, *, reason):
    require_role(by, *EVERYONE)
    quotation = _lock(quotation)
    if quotation.is_draft:
        raise ValidationError("Delete a draft instead of voiding it.")
    if quotation.is_void:
        raise ValidationError(f"{quotation.label} is already void.")
    if quotation.invoices.exclude(status=Invoice.Status.VOID).exists():
        raise ValidationError("This quotation has an invoice. Void the invoice first.")
    if not (reason or "").strip():
        raise ValidationError("Say why it is being voided.")
    quotation.status, quotation.voided_at, quotation.void_reason = Status.VOID, timezone.now(), reason.strip()
    quotation.save(update_fields=["status", "voided_at", "void_reason", "updated_at"])
    return quotation


@service
@transaction.atomic
def delete_draft(quotation, by):
    require_role(by, *EVERYONE)
    quotation = _lock(quotation)
    assert_draft(quotation)
    quotation.delete()
