from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.billing.models import Invoice, Receipt
from apps.core.async_utils import service
from apps.core.permissions import MONEY, require_role
from apps.finance.models import Transaction

from .common import today


@service
@transaction.atomic
def record_payment(invoice, by, *, amount, date, account, reference="", being_payment_for="", received_from=""):
    """Money received against an issued invoice. In one step: the receipt (numbered from the payment date),
    the money-in transaction on `account`, and the invoice's paid amount and status."""
    require_role(by, *MONEY)
    invoice = Invoice.objects.select_for_update().select_related("client").get(pk=invoice.pk)
    amount = Decimal(amount)
    if not invoice.is_open:
        raise ValidationError(f"{invoice.label} is {invoice.get_status_display().lower()}: it cannot take a payment.")
    if amount <= 0:
        raise ValidationError("The amount must be more than 0.")
    if amount > invoice.balance:
        raise ValidationError(f"That is more than the balance of {invoice.currency} {invoice.balance:,.0f}.")
    if date > today():
        raise ValidationError("The payment date cannot be in the future.")
    if invoice.date and date < invoice.date:
        raise ValidationError(f"The payment date cannot be before the invoice date ({invoice.date:%d/%m/%Y}).")
    if not account.is_active:
        raise ValidationError(f"{account} is closed. Choose another account.")

    receipt = Receipt.objects.create(
        invoice=invoice, date=date, amount=amount, account=account, reference=reference.strip(),
        received_from=received_from.strip() or invoice.client.name,
        being_payment_for=being_payment_for.strip() or f"Payment on invoice {invoice.number}.",
        invoice_total=invoice.total, previously_paid=invoice.amount_paid, received_by=by,
    )
    Transaction.objects.create(
        account=account, direction=Transaction.Direction.IN, kind=Transaction.Kind.RECEIPT, amount=amount, date=date,
        description=f"{receipt.number} from {receipt.received_from} ({invoice.number})", reference=receipt.reference,
        receipt=receipt, created_by=by,
    )
    invoice.refresh_payments()
    return receipt


@service
@transaction.atomic
def void_receipt(receipt, by, *, reason):
    """Undo a payment recorded by mistake: the money leaves the account again and the invoice owes it again."""
    require_role(by, *MONEY)
    receipt = Receipt.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status == Receipt.Status.VOID:
        raise ValidationError(f"{receipt.number} is already void.")
    if not (reason or "").strip():
        raise ValidationError("Say why it is being voided.")
    receipt.status, receipt.voided_at, receipt.void_reason = Receipt.Status.VOID, timezone.now(), reason.strip()
    receipt.save(update_fields=["status", "voided_at", "void_reason", "updated_at"])
    receipt.transactions.update(is_void=True)
    Invoice.objects.select_for_update().get(pk=receipt.invoice_id).refresh_payments()
    return receipt
