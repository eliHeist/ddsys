from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from simple_history.models import HistoricalRecords

from apps.core.models import TimeStampedModel


class Loan(TimeStampedModel):
    """Money the company owes back to someone who put in their own: a director, any staff member, or an outside
    lender. Two ways it arrives:

    - into one of our accounts (`account` set): a loan or a top-up, a money-in line on that account
      (finance.loans.record_loan);
    - spent straight on company costs from their own pocket (`account` empty): a claim. Someone paid all or part
      of an expense themselves, say the cash they were given ran short on site. The expense is recorded with
      this as how (part of) it was paid (finance.services.record_expense), and no account moves for that part.

    `must_repay` says whether the company owes it back. One that must be repaid is paid back (reimbursed) in
    parts (LoanRepayment); one that need not (a gift, or capital put in) stays on record with nothing owed.
    """

    class Status(models.TextChoices):
        VALID = "valid", "Valid"
        VOID = "void", "Void"

    person = models.ForeignKey("core.StaffProfile", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="loans", help_text="The director or staff member it came from, if one of ours")
    lender_name = models.CharField(max_length=150, help_text="Who it came from (our person's name, or the outside lender)")
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    account = models.ForeignKey("finance.Account", null=True, blank=True, on_delete=models.PROTECT, related_name="loans",
                                help_text="Where the money went. Empty when the lender paid company costs directly")
    must_repay = models.BooleanField(default=True, help_text="The company has to pay it back")
    purpose = models.CharField(max_length=255, help_text="What it was for")
    reference = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VALID)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta:
        ordering = ("-date", "-created_at")
        constraints = (models.CheckConstraint(condition=models.Q(amount__gt=0), name="loan_amount_positive"),)

    def __str__(self):
        return f"{self.amount:,.0f} from {self.lender_name}"

    @property
    def is_void(self):
        return self.status == self.Status.VOID

    @property
    def from_director(self):
        return self.person_id is not None and self.person.is_director

    @property
    def lender_kind(self):
        """Director, Staff or Outside lender: how the lists group what is owed."""
        if self.person_id is None:
            return "Outside lender"
        return "Director" if self.person.is_director else "Staff"

    @property
    def paid_costs_directly(self):
        """A claim: they paid company costs themselves, rather than lending money into an account."""
        return self.account_id is None

    @property
    def title(self):
        return f"{'Paid by' if self.paid_costs_directly else 'Loan from'} {self.lender_name}"

    def repaid_total(self):
        """What has been paid back so far (valid repayments). Selectors annotate `repaid` instead for lists."""
        return self.repayments.filter(status="valid").aggregate(s=Sum("amount"))["s"] or Decimal(0)  # pyright: ignore[reportAttributeAccessIssue]

    def balance_with(self, repaid):
        """What is still owed, given what was repaid: nothing for a void loan or one that need not be repaid."""
        if self.is_void or not self.must_repay:
            return Decimal(0)
        return max(self.amount - repaid, Decimal(0))
