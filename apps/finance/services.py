"""Money services. Each one writes its transactions in the same database transaction as the record it belongs
to, so an account balance can never disagree with the receipts, expenses and transfers behind it."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.async_utils import service
from apps.core.permissions import ADMINS, MONEY, require_role

from .models import Expense, Transaction, Transfer

IN, OUT = Transaction.Direction.IN, Transaction.Direction.OUT
Kind = Transaction.Kind


def _check_amount(amount):
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError("The amount must be more than 0.")
    return amount


def _check_date(date):
    if date > timezone.localdate():
        raise ValidationError("The date cannot be in the future.")


def _check_account(account):
    if not account.is_active:
        raise ValidationError(f"{account} is closed. Choose another account.")


@service
@transaction.atomic
def record_expense(by, *, date, amount, account, category, description, project=None, payee="", reference="",
                   attachment=None):
    require_role(by, *MONEY)
    amount = _check_amount(amount)
    _check_date(date)
    _check_account(account)
    expense = Expense.objects.create(
        date=date, amount=amount, account=account, category=category, project=project, payee=payee.strip(),
        description=description.strip(), reference=reference.strip(), created_by=by,
        **({"attachment": attachment} if attachment else {}),
    )
    Transaction.objects.create(
        account=account, direction=OUT, kind=Kind.EXPENSE, amount=amount, date=date, reference=expense.reference,
        description=f"{category}: {expense.description}" + (f" ({expense.payee})" if expense.payee else ""),
        expense=expense, created_by=by,
    )
    return expense


@service
@transaction.atomic
def void_expense(expense, by, *, reason):
    require_role(by, *MONEY)
    expense = Expense.objects.select_for_update().get(pk=expense.pk)
    if expense.status == Expense.Status.VOID:
        raise ValidationError("This expense is already void.")
    if not (reason or "").strip():
        raise ValidationError("Say why it is being voided.")
    expense.status, expense.voided_at, expense.void_reason = Expense.Status.VOID, timezone.now(), reason.strip()
    expense.save(update_fields=["status", "voided_at", "void_reason", "updated_at"])
    expense.transactions.update(is_void=True)
    return expense


@service
@transaction.atomic
def record_transfer(by, *, date, from_account, to_account, amount, fee=0, note="", reference=""):
    """Move money between two of our accounts. Not income or spending, except the fee, which is an expense-like
    transaction out of the sending account."""
    require_role(by, *MONEY)
    amount, fee = _check_amount(amount), Decimal(fee or 0)
    _check_date(date)
    _check_account(from_account)
    _check_account(to_account)
    if from_account.pk == to_account.pk:
        raise ValidationError("Choose two different accounts.")
    if fee < 0:
        raise ValidationError("The fee cannot be negative.")
    transfer = Transfer.objects.create(date=date, from_account=from_account, to_account=to_account, amount=amount,
                                       fee=fee, note=note.strip(), reference=reference.strip(), created_by=by)
    common = {"kind": Kind.TRANSFER, "date": date, "transfer": transfer, "reference": transfer.reference, "created_by": by}
    Transaction.objects.create(account=from_account, direction=OUT, amount=amount,
                               description=f"Transfer to {to_account}" + (f": {transfer.note}" if transfer.note else ""), **common)
    Transaction.objects.create(account=to_account, direction=IN, amount=amount,
                               description=f"Transfer from {from_account}" + (f": {transfer.note}" if transfer.note else ""), **common)
    if fee:
        Transaction.objects.create(account=from_account, direction=OUT, amount=fee,
                                   description=f"Fee on transfer to {to_account}", **{**common, "kind": Kind.FEE})
    return transfer


@service
@transaction.atomic
def void_transfer(transfer, by):
    require_role(by, *MONEY)
    transfer = Transfer.objects.select_for_update().get(pk=transfer.pk)
    if transfer.status == Transfer.Status.VOID:
        raise ValidationError("This transfer is already void.")
    transfer.status, transfer.voided_at = Transfer.Status.VOID, timezone.now()
    transfer.save(update_fields=["status", "voided_at", "updated_at"])
    transfer.transactions.update(is_void=True)
    return transfer


@service
@transaction.atomic
def record_other_income(by, *, account, amount, date, description, reference=""):
    """Money in that is not a client payment on an invoice: a refund, interest, a loan from the directors..."""
    require_role(by, *MONEY)
    amount = _check_amount(amount)
    _check_date(date)
    _check_account(account)
    if not description.strip():
        raise ValidationError("Say what the money is.")
    return Transaction.objects.create(account=account, direction=IN, kind=Kind.OTHER_INCOME, amount=amount, date=date,
                                      description=description.strip(), reference=reference.strip(), created_by=by)


@service
@transaction.atomic
def record_adjustment(by, *, account, direction, amount, date, reason):
    """Admins only: correct an account so it matches the real statement (bank charges, a count that was off).
    The reason is kept on the transaction."""
    require_role(by, *ADMINS)
    amount = _check_amount(amount)
    _check_date(date)
    if direction not in (IN, OUT):
        raise ValidationError("Choose money in or money out.")
    if not (reason or "").strip():
        raise ValidationError("Say why the account is being adjusted.")
    return Transaction.objects.create(account=account, direction=direction, kind=Kind.ADJUSTMENT, amount=amount,
                                      date=date, description=f"Adjustment: {reason.strip()}", created_by=by)


@service
@transaction.atomic
def void_transaction(txn, by):
    """Only standalone transactions (other income, adjustments) are voided directly; the rest go with their record."""
    require_role(by, *ADMINS)
    txn = Transaction.objects.select_for_update().get(pk=txn.pk)
    if txn.kind not in (Kind.OTHER_INCOME, Kind.ADJUSTMENT):
        raise ValidationError("Void the receipt, expense or transfer this belongs to instead.")
    txn.is_void = True
    txn.save(update_fields=["is_void", "updated_at"])
    return txn
