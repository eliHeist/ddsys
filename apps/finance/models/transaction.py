from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Transaction(TimeStampedModel):
    """One movement of money into or out of an account: the record every balance is worked out from.

    Transactions are made by services only (a receipt, an expense, a transfer or an adjustment), never typed
    in by hand, and never deleted: voiding the receipt or expense voids its transaction too.
    """

    class Direction(models.TextChoices):
        IN = "in", "Money in"
        OUT = "out", "Money out"

    class Kind(models.TextChoices):
        RECEIPT = "receipt", "Client payment"
        EXPENSE = "expense", "Expense"
        TRANSFER = "transfer", "Transfer"
        FEE = "fee", "Transfer fee"
        ADJUSTMENT = "adjustment", "Adjustment"
        OTHER_INCOME = "other_income", "Other income"

    account = models.ForeignKey("finance.Account", on_delete=models.PROTECT, related_name="transactions")
    direction = models.CharField(max_length=3, choices=Direction.choices)
    kind = models.CharField(max_length=15, choices=Kind.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2, help_text="Always positive; the direction gives the sign")
    date = models.DateField()
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=80, blank=True)
    receipt = models.ForeignKey("billing.Receipt", null=True, blank=True, on_delete=models.PROTECT, related_name="transactions")
    expense = models.ForeignKey("finance.Expense", null=True, blank=True, on_delete=models.PROTECT, related_name="transactions")
    transfer = models.ForeignKey("finance.Transfer", null=True, blank=True, on_delete=models.PROTECT, related_name="transactions")
    is_void = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ("-date", "-created_at")
        constraints = (
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="transaction_amount_positive"),
        )

    def __str__(self):
        return f"{self.get_direction_display()} {self.amount} - {self.description}"

    @property
    def signed_amount(self):
        return self.amount if self.direction == self.Direction.IN else -self.amount
