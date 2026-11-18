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


def _check_fee(fee, amount=None):
    fee = Decimal(fee or 0)
    if fee < 0:
        raise ValidationError("The fee cannot be negative.")
    if amount is not None and fee >= amount:
        raise ValidationError("The fee must be less than the amount.")
    return fee


def record_fee(*, account, amount, date, description, by, reference="", **link):
    """The fee line: money out of `account`, linked (receipt=, expense=, transfer= or loan_repayment=) to what it
    was charged on.
    Call from inside another service's transaction; does nothing for a zero fee."""
    if amount:
        return Transaction.objects.create(account=account, direction=OUT, kind=Kind.FEE, amount=amount, date=date,
                                          description=description, reference=reference, created_by=by, **link)


@service
@transaction.atomic
def record_expense(by, *, date, amount, category, description, account=None, paid_by=None, paid_by_amount=None,
                   must_repay=True, project=None, payee="", reference="", attachment=None, fee=0):
    """Money spent. Three ways it can be paid:

    - all from `account`: the money leaves the account, and a `fee` for paying it is its own line there;
    - all by someone from their own money (`paid_by`, a StaffProfile: a director or any staff member): no
      account moves, and what they paid is recorded as owed back to them (a claim, to be reimbursed if
      `must_repay`);
    - split: part from `account` and part (`paid_by_amount`) by `paid_by`, say the cash they were given ran
      short on site and they topped it up themselves. The account pays the rest.

    Either way the whole amount counts as the expense, in its category and project."""
    from .loans import new_loan

    require_role(by, *MONEY)
    amount = _check_amount(amount)
    fee = _check_fee(fee)
    _check_date(date)
    if account is None and paid_by is None:
        raise ValidationError("Choose the account it was paid from, or who paid it themselves (or both, if they shared it).")
    personal = Decimal(0)
    if paid_by is not None:
        personal = amount if paid_by_amount in (None, "") else _check_amount(paid_by_amount)
        if account is None and personal != amount:
            raise ValidationError("With no account, they paid it all: leave their part empty, or choose the account for the rest.")
        if account is not None and personal >= amount:
            raise ValidationError(f"Their part must be less than the {amount:,.0f}, or choose no account if they paid it all.")
    if account is not None:
        _check_account(account)
    elif fee:
        raise ValidationError("Leave the fee at 0 when no account paid: add any charge they paid to the amount.")

    loan = None
    if paid_by is not None:
        loan = new_loan(by, amount=personal, date=date, person=paid_by, must_repay=must_repay, reference=reference,
                        purpose=f"Paid for {category}: {description.strip()}")
    expense = Expense.objects.create(
        date=date, amount=amount, fee=fee, account=account, loan=loan, category=category, project=project,
        payee=payee.strip(), description=description.strip(), reference=reference.strip(), created_by=by,
        **({"attachment": attachment} if attachment else {}),
    )
    if account is None:
        return expense
    paid_by_note = f", {personal:,.0f} paid by {loan.lender_name}" if loan else ""
    Transaction.objects.create(
        account=account, direction=OUT, kind=Kind.EXPENSE, amount=amount - personal, date=date, reference=expense.reference,
        description=f"{category}: {expense.description}" + (f" ({expense.payee})" if expense.payee else "") + paid_by_note,
        expense=expense, created_by=by,
    )
    record_fee(account=account, amount=fee, date=date, reference=expense.reference, expense=expense, by=by,
               description=f"Fee on: {expense.description}" + (f" ({expense.payee})" if expense.payee else ""))
    return expense


@service
@transaction.atomic
def void_expense(expense, by, *, reason):
    """Undo an expense: the money goes back into its account, and if someone paid (part of) it themselves, what is
    owed to them for it is voided too (refused once some of it has been paid back)."""
    from .loans import void_loan_record
    from .models import Loan

    require_role(by, *MONEY)
    expense = Expense.objects.select_for_update().get(pk=expense.pk)
    if expense.status == Expense.Status.VOID:
        raise ValidationError("This expense is already void.")
    if not (reason or "").strip():
        raise ValidationError("Say why it is being voided.")
    if expense.loan_id:
        void_loan_record(Loan.objects.select_for_update().get(pk=expense.loan_id), f"Expense voided: {reason.strip()}")
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
    amount, fee = _check_amount(amount), _check_fee(fee)
    _check_date(date)
    _check_account(from_account)
    _check_account(to_account)
    if from_account.pk == to_account.pk:
        raise ValidationError("Choose two different accounts.")
    transfer = Transfer.objects.create(date=date, from_account=from_account, to_account=to_account, amount=amount,
                                       fee=fee, note=note.strip(), reference=reference.strip(), created_by=by)
    common = {"kind": Kind.TRANSFER, "date": date, "transfer": transfer, "reference": transfer.reference, "created_by": by}
    Transaction.objects.create(account=from_account, direction=OUT, amount=amount,
                               description=f"Transfer to {to_account}" + (f": {transfer.note}" if transfer.note else ""), **common)
    Transaction.objects.create(account=to_account, direction=IN, amount=amount,
                               description=f"Transfer from {from_account}" + (f": {transfer.note}" if transfer.note else ""), **common)
    record_fee(account=from_account, amount=fee, date=date, reference=transfer.reference, transfer=transfer, by=by,
               description=f"Fee on transfer to {to_account}")
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
def record_other_income(by, *, account, amount, date, description, reference="", project=None):
    """Money in that is not a client payment on an invoice: a product's direct sales or app-store payout, a refund,
    interest, capital from the directors... Linked to a `project`, it counts in that project's (product's) income."""
    require_role(by, *MONEY)
    amount = _check_amount(amount)
    _check_date(date)
    _check_account(account)
    if not description.strip():
        raise ValidationError("Say what the money is.")
    return Transaction.objects.create(account=account, direction=IN, kind=Kind.OTHER_INCOME, amount=amount, date=date,
                                      description=description.strip(), reference=reference.strip(), project=project,
                                      created_by=by)


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
    """Only standalone transactions (other income, adjustments) are voided directly; the rest go with their record
    (a receipt, expense, transfer, loan or repayment)."""
    require_role(by, *ADMINS)
    txn = Transaction.objects.select_for_update().get(pk=txn.pk)
    if txn.kind not in (Kind.OTHER_INCOME, Kind.ADJUSTMENT):
        raise ValidationError("Void the receipt, expense, transfer or loan this belongs to instead.")
    txn.is_void = True
    txn.save(update_fields=["is_void", "updated_at"])
    return txn
