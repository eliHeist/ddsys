from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import TimeStampedModel


class LoanRepayment(TimeStampedModel):
    """Part (or all) of a loan paid back: money out of one of our accounts to the lender, with any fee as its own line."""

    class Status(models.TextChoices):
        VALID = "valid", "Valid"
        VOID = "void", "Void"

    loan = models.ForeignKey("finance.Loan", on_delete=models.PROTECT, related_name="repayments")
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    fee = models.DecimalField(max_digits=14, decimal_places=2, default=0, help_text="Charge for sending it, on top")
    account = models.ForeignKey("finance.Account", on_delete=models.PROTECT, related_name="loan_repayments",
                                help_text="Where the money was paid from")
    reference = models.CharField(max_length=80, blank=True)
    note = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VALID)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta:
        ordering = ("date", "created_at")
        constraints = (models.CheckConstraint(condition=models.Q(amount__gt=0), name="loan_repayment_amount_positive"),)

    def __str__(self):
        return f"{self.amount:,.0f} back to {self.loan.lender_name}"

    @property
    def is_void(self):
        return self.status == self.Status.VOID
