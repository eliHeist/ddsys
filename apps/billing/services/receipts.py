"""Money from clients: payments on invoices, deposits made before there is an invoice, and the credit between.

A receipt is the money (it lands in an account the day it is recorded). Allocations say which invoices it paid.
Whatever part of a receipt is not allocated is the client's credit, and can be applied to their invoices later:
by hand (apply_credit) or automatically when an invoice for the same quotation or project is issued (auto_apply).
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.billing.models import Allocation, Invoice, Receipt
from apps.core.async_utils import service
from apps.core.permissions import MONEY, require_role
from apps.finance.models import Transaction
from apps.finance.services import record_fee

from .common import assert_project_matches, today

ZERO = Decimal(0)


def _check_money(amount, fee, date, account):
    if amount <= 0:
        raise ValidationError("The amount must be more than 0.")
    if fee < 0 or fee >= amount:
        raise ValidationError("The fee must be 0 or more, and less than the amount.")
    if date > today():
        raise ValidationError("The payment date cannot be in the future.")
    if not account.is_active:
        raise ValidationError(f"{account} is closed. Choose another account.")


def _bank_it(receipt, by, *, what):
    """The money-in line (and its fee line) for a new receipt."""
    Transaction.objects.create(
        account=receipt.account, direction=Transaction.Direction.IN, kind=Transaction.Kind.RECEIPT, amount=receipt.amount,
        date=receipt.date, description=f"{receipt.number} from {receipt.received_from} ({what})",
        reference=receipt.reference, receipt=receipt, created_by=by,
    )
    record_fee(account=receipt.account, amount=receipt.fee, date=receipt.date, reference=receipt.reference,
               receipt=receipt, by=by, description=f"Fee on {receipt.number} from {receipt.received_from}")


def _allocate(receipt, invoice, amount, by):
    Allocation.objects.create(receipt=receipt, invoice=invoice, amount=amount, date=today(), created_by=by)
    invoice.refresh_payments()


def unapplied(receipt):
    """How much of a receipt is still credit."""
    if receipt.status != Receipt.Status.VALID:
        return ZERO
    used = receipt.allocations.aggregate(s=Sum("amount"))["s"] or ZERO
    return receipt.amount - used


def credit_receipts(client, *, only=None):
    """The client's valid receipts that still have credit, oldest first, each with `.credit` set.
    `only` narrows them (a Q on Receipt), e.g. to one quotation's deposits."""
    receipts = (Receipt.objects.select_for_update().filter(client=client, status=Receipt.Status.VALID)
                .order_by("date", "id"))
    if only is not None:
        receipts = receipts.filter(only)
    found = []
    for receipt in receipts:
        receipt.credit = unapplied(receipt)
        if receipt.credit > 0:
            found.append(receipt)
    return found


@service
@transaction.atomic
def record_payment(invoice, by, *, amount, date, account, reference="", being_payment_for="", received_from="", fee=0):
    """Money received against an issued invoice. In one step: the receipt (numbered from the payment date), the
    money-in transaction on `account`, and the invoice's paid amount and status. Anything above the balance stays
    with the client as credit for a later invoice.

    `fee` is a charge taken off on the way in (e.g. mobile money). The client is still credited the full `amount`;
    the account gets `amount` in and the fee out as its own line, so it ends up with what actually arrived."""
    require_role(by, *MONEY)
    invoice = Invoice.objects.select_for_update().select_related("client").get(pk=invoice.pk)
    amount, fee = Decimal(amount), Decimal(fee or 0)
    if not invoice.is_open:
        raise ValidationError(f"{invoice.label} is {invoice.get_status_display().lower()}: it cannot take a payment.")
    _check_money(amount, fee, date, account)
    if invoice.date and date < invoice.date:
        raise ValidationError(f"The payment date cannot be before the invoice date ({invoice.date:%d/%m/%Y}). "
                              "Money that came before the invoice is a deposit: record it on the client's page.")

    receipt = Receipt.objects.create(
        client=invoice.client, invoice=invoice, project=invoice.project, quotation=invoice.quotation,
        date=date, amount=amount, fee=fee, account=account, reference=reference.strip(),
        received_from=received_from.strip() or invoice.client.name,
        being_payment_for=being_payment_for.strip() or f"Payment on invoice {invoice.number}.",
        invoice_total=invoice.total, previously_paid=invoice.amount_paid, received_by=by,
    )
    _bank_it(receipt, by, what=invoice.number)
    _allocate(receipt, invoice, min(amount, invoice.balance), by)
    return receipt


@service
@transaction.atomic
def record_deposit(client, by, *, amount, date, account, quotation=None, project=None, reference="",
                   being_payment_for="", received_from="", fee=0):
    """Money a client paid before there is an invoice for it. It goes into the account now and is the client's
    credit until applied. With a quotation or project, it is applied automatically when an invoice for that
    quotation or project is issued."""
    require_role(by, *MONEY)
    amount, fee = Decimal(amount), Decimal(fee or 0)
    _check_money(amount, fee, date, account)
    if quotation is not None:
        if quotation.client_id != client.pk:
            raise ValidationError(f"{quotation.label} is for {quotation.client}, not {client}.")
        if quotation.is_draft or quotation.is_void:
            raise ValidationError(f"{quotation.label} is {quotation.get_status_display().lower()}: issue it first.")
        project = project or quotation.project
    assert_project_matches(client, project)

    if quotation is not None:
        default_for = f"Deposit on quotation {quotation.number}."
    elif project is not None:
        default_for = f"Deposit for {project.title}."
    else:
        default_for = "Payment on account."
    receipt = Receipt.objects.create(
        client=client, quotation=quotation, project=project, date=date, amount=amount, fee=fee, account=account,
        reference=reference.strip(), received_from=received_from.strip() or client.name,
        being_payment_for=being_payment_for.strip() or default_for, received_by=by,
    )
    _bank_it(receipt, by, what="deposit")
    return receipt


@service
@transaction.atomic
def apply_credit(invoice, by, *, amount=None, receipt=None):
    """Use the client's credit to pay an issued invoice: from one receipt if given, otherwise from the oldest
    credit first. `amount` defaults to as much as the credit and the balance allow. Returns the amount applied."""
    require_role(by, *MONEY)
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if not invoice.is_open:
        raise ValidationError(f"{invoice.label} is {invoice.get_status_display().lower()}: there is nothing to pay.")
    if receipt is not None and receipt.client_id != invoice.client_id:
        raise ValidationError(f"{receipt.number} is {receipt.client}'s money, not {invoice.client}'s.")
    sources = credit_receipts(invoice.client, only=Q(pk=receipt.pk) if receipt is not None else None)
    available = sum((r.credit for r in sources), ZERO)
    if available <= 0:
        raise ValidationError(f"{receipt.number} has no credit left." if receipt else f"{invoice.client} has no credit.")
    wanted = min(available, invoice.balance) if amount in (None, "") else Decimal(amount)
    if wanted <= 0:
        raise ValidationError("The amount must be more than 0.")
    if wanted > invoice.balance:
        raise ValidationError(f"That is more than the balance of {invoice.currency} {invoice.balance:,.0f}.")
    if wanted > available:
        raise ValidationError(f"That is more than the credit of {invoice.currency} {available:,.0f}.")
    return _spend(sources, invoice, wanted, by)


def _spend(sources, invoice, wanted, by):
    left = wanted
    for source in sources:
        if left <= 0:
            break
        part = min(source.credit, left)
        Allocation.objects.create(receipt=source, invoice=invoice, amount=part, date=today(), created_by=by)
        left -= part
    invoice.refresh_payments()
    return wanted - left


def auto_apply(invoice, by=None):
    """Apply deposits made for this invoice's quotation or project. Runs when an invoice is issued (inside that
    transaction, so no permission check). Other credit is left for someone to apply by hand. Returns the amount."""
    links = Q()
    if invoice.quotation_id:
        links |= Q(quotation_id=invoice.quotation_id)
    if invoice.project_id:
        links |= Q(project_id=invoice.project_id)
    if not links or invoice.balance <= 0:
        return ZERO
    sources = credit_receipts(invoice.client, only=links & Q(invoice__isnull=True))
    wanted = min(sum((r.credit for r in sources), ZERO), invoice.balance)
    return _spend(sources, invoice, wanted, by) if wanted > 0 else ZERO


@service
@transaction.atomic
def remove_allocation(allocation, by):
    """Take back credit applied to the wrong invoice. The money stays the client's credit; the invoice owes it again."""
    require_role(by, *MONEY)
    allocation = Allocation.objects.select_for_update().select_related("invoice").get(pk=allocation.pk)
    invoice = Invoice.objects.select_for_update().get(pk=allocation.invoice_id)
    if invoice.is_void:
        raise ValidationError(f"{invoice.label} is void.")
    allocation.delete()
    invoice.refresh_payments()


def release(invoice):
    """Free everything paid towards an invoice being voided: the money becomes the client's credit again."""
    invoice.allocations.all().delete()


@service
@transaction.atomic
def void_receipt(receipt, by, *, reason):
    """Undo money recorded by mistake: it (and its fee line) leaves the account again, and every invoice it paid
    owes that part again."""
    require_role(by, *MONEY)
    receipt = Receipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status == Receipt.Status.VOID:
        raise ValidationError(f"{receipt.number} is already void.")
    if not (reason or "").strip():
        raise ValidationError("Say why it is being voided.")
    receipt.status, receipt.voided_at, receipt.void_reason = Receipt.Status.VOID, timezone.now(), reason.strip()
    receipt.save(update_fields=["status", "voided_at", "void_reason", "updated_at"])
    receipt.transactions.update(is_void=True)
    for invoice_id in set(receipt.allocations.values_list("invoice_id", flat=True)):
        Invoice.objects.select_for_update().get(pk=invoice_id).refresh_payments()
    return receipt
