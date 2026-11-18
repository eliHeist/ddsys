"""Money the company owes back, and paying it back. Each service writes its account lines in the same database
transaction as the record, like the rest of finance.services.

It comes from one of our people (a director or any staff member: pick them) or someone outside (type the name).
It either lands in one of our accounts (a loan or top-up: record_loan), or was spent straight on company costs
from their own pocket (a claim: finance.services.record_expense with `paid_by`). If it must be repaid, it is
paid back (reimbursed) in parts until nothing is owed.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.async_utils import service
from apps.core.permissions import MONEY, require_role

from .models import Loan, LoanRepayment, Transaction
from .services import _check_account, _check_amount, _check_date, _check_fee, record_fee

IN, OUT = Transaction.Direction.IN, Transaction.Direction.OUT
Kind = Transaction.Kind


def lender_name_for(person, lender_name):
    """Our person's name, or the outside lender's. Exactly one of the two."""
    lender_name = (lender_name or "").strip()
    if person is not None and lender_name and lender_name != person.name:
        raise ValidationError("Choose one of our people or type the lender's name, not both.")
    if person is not None:
        return person.name
    if not lender_name:
        raise ValidationError("Choose who it came from, or type the lender's name.")
    return lender_name


def new_loan(by, *, amount, date, purpose, person=None, lender_name="", account=None, must_repay=True, reference=""):
    """The loan record alone (no account line). For services already inside a transaction (record_loan,
    finance.services.record_expense)."""
    amount = _check_amount(amount)
    _check_date(date)
    if not (purpose or "").strip():
        raise ValidationError("Say what the loan is for.")
    return Loan.objects.create(
        person=person, lender_name=lender_name_for(person, lender_name), date=date, amount=amount,
        account=account, must_repay=bool(must_repay), purpose=purpose.strip(), reference=(reference or "").strip(),
        created_by=by,
    )


@service
@transaction.atomic
def record_loan(by, *, amount, date, account, purpose, person=None, lender_name="", must_repay=True, reference=""):
    """Money lent to the company and received into `account`: a loan, or someone topping up an account so it can
    pay for something."""
    require_role(by, *MONEY)
    _check_account(account)
    loan = new_loan(by, amount=amount, date=date, purpose=purpose, person=person, lender_name=lender_name,
                    account=account, must_repay=must_repay, reference=reference)
    Transaction.objects.create(account=account, direction=IN, kind=Kind.LOAN, amount=loan.amount, date=date,
                               description=f"Loan from {loan.lender_name}: {loan.purpose}", reference=loan.reference,
                               loan=loan, created_by=by)
    return loan


def repaid(loan):
    return loan.repayments.filter(status=LoanRepayment.Status.VALID).aggregate(s=Sum("amount"))["s"] or Decimal(0)


@service
@transaction.atomic
def repay_loan(loan, by, *, amount, date, account, fee=0, reference="", note=""):
    """Pay back part (or the rest) of a loan from `account`. A fee for sending it is its own line."""
    require_role(by, *MONEY)
    loan = Loan.objects.select_for_update().get(pk=loan.pk)
    amount, fee = _check_amount(amount), _check_fee(fee)
    _check_date(date)
    _check_account(account)
    if loan.is_void:
        raise ValidationError("This loan is void.")
    if not loan.must_repay:
        raise ValidationError("This loan is not to be repaid. Mark it as to be refunded first.")
    owed = loan.balance_with(repaid(loan))
    if amount > owed:
        raise ValidationError(f"That is more than what is owed ({owed:,.0f}).")
    if date < loan.date:
        raise ValidationError(f"The repayment cannot be before the loan ({loan.date:%d/%m/%Y}).")
    repayment = LoanRepayment.objects.create(loan=loan, date=date, amount=amount, fee=fee, account=account,
                                             reference=(reference or "").strip(), note=(note or "").strip(), created_by=by)
    Transaction.objects.create(account=account, direction=OUT, kind=Kind.LOAN_REPAYMENT, amount=amount, date=date,
                               description=f"Loan repayment to {loan.lender_name}" + (f": {repayment.note}" if repayment.note else ""),
                               reference=repayment.reference, loan=loan, loan_repayment=repayment, created_by=by)
    record_fee(account=account, amount=fee, date=date, reference=repayment.reference, loan_repayment=repayment, by=by,
               description=f"Fee on loan repayment to {loan.lender_name}")
    return repayment


@service
@transaction.atomic
def set_must_repay(loan, by, *, must_repay):
    """Change whether the company owes it back (say a director turns a loan into capital, or the other way)."""
    require_role(by, *MONEY)
    loan = Loan.objects.select_for_update().get(pk=loan.pk)
    if loan.is_void:
        raise ValidationError("This loan is void.")
    loan.must_repay = bool(must_repay)
    loan.save(update_fields=["must_repay", "updated_at"])
    return loan


def void_loan_record(loan, reason):
    """Void a locked loan and its lines; no permission check (for void_loan and finance.services.void_expense)."""
    if loan.repayments.filter(status=LoanRepayment.Status.VALID).exists():
        raise ValidationError("Part of this has been paid back. Void the repayments first.")
    loan.status, loan.voided_at, loan.void_reason = Loan.Status.VOID, timezone.now(), reason
    loan.save(update_fields=["status", "voided_at", "void_reason", "updated_at"])
    loan.transactions.update(is_void=True)


@service
@transaction.atomic
def void_loan(loan, by, *, reason):
    """Undo a loan recorded by mistake: its money leaves the account again."""
    require_role(by, *MONEY)
    loan = Loan.objects.select_for_update().get(pk=loan.pk)
    if loan.is_void:
        raise ValidationError("This loan is already void.")
    if not (reason or "").strip():
        raise ValidationError("Say why it is being voided.")
    if loan.expenses.filter(status="valid").exists():
        raise ValidationError("This is someone paying an expense themselves. Void the expense instead.")
    void_loan_record(loan, reason.strip())
    return loan


@service
@transaction.atomic
def void_repayment(repayment, by, *, reason):
    """Undo a repayment recorded by mistake: the money comes back into the account and the loan is owed again."""
    require_role(by, *MONEY)
    repayment = LoanRepayment.objects.select_for_update().get(pk=repayment.pk)
    if repayment.is_void:
        raise ValidationError("This repayment is already void.")
    if not (reason or "").strip():
        raise ValidationError("Say why it is being voided.")
    repayment.status, repayment.voided_at, repayment.void_reason = LoanRepayment.Status.VOID, timezone.now(), reason.strip()
    repayment.save(update_fields=["status", "voided_at", "void_reason", "updated_at"])
    repayment.transactions.update(is_void=True)
    return repayment
