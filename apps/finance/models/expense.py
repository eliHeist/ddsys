from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import TimeStampedModel


class Expense(TimeStampedModel):
    """Money spent: printing, transport, data, salaries... Linking it to a project counts it in that
    project's costs. Recording one takes the money out of the chosen account. When someone (a director or any
    staff member) paid all or part of it from their own money, `loan` is set: what the company owes them back.
    Only the rest (`account_amount`) leaves the account, and with no account at all, none does."""

    class Status(models.TextChoices):
        VALID = "valid", "Valid"
        VOID = "void", "Void"

    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    fee = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                              help_text="Mobile money or bank charge for paying it, on top of the amount")
    account = models.ForeignKey("finance.Account", null=True, blank=True, on_delete=models.PROTECT, related_name="expenses",
                                help_text="Where the money was paid from. Empty when someone paid it all themselves")
    loan = models.ForeignKey("finance.Loan", null=True, blank=True, on_delete=models.PROTECT, related_name="expenses",
                             help_text="The part someone paid from their own money, owed back to them")
    category = models.ForeignKey("finance.ExpenseCategory", on_delete=models.PROTECT, related_name="expenses")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="expenses")
    payee = models.CharField(max_length=150, blank=True, help_text="Who was paid")
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=80, blank=True, help_text="Receipt, mobile money or bank transaction ID")
    attachment = models.FileField(upload_to="expenses/%Y/%m/", blank=True, help_text="Photo or PDF of the receipt")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VALID)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta:
        ordering = ("-date", "-created_at")

    def __str__(self):
        return self.description

    @property
    def personal_amount(self):
        """What someone paid from their own pocket (owed back to them)."""
        return self.loan.amount if self.loan_id else 0

    @property
    def account_amount(self):
        """What left the company account (the fee comes on top)."""
        return self.amount - self.personal_amount if self.account_id else 0

    @property
    def total_cost(self):
        return self.amount + self.fee
