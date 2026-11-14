from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import TimeStampedModel


class Account(TimeStampedModel):
    """Somewhere money is kept: a bank account, a mobile money number or the cash box.

    Its balance is never typed in: it is the opening balance plus every valid transaction
    (finance.selectors.balances). Accounts marked `show_on_documents` print under "Payment Methods".
    """

    class Kind(models.TextChoices):
        BANK = "bank", "Bank"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        CASH = "cash", "Cash"

    name = models.CharField(max_length=80, unique=True, help_text='As documents print it, e.g. "Stanbic Bank"')
    kind = models.CharField(max_length=15, choices=Kind.choices, default=Kind.BANK)
    account_number = models.CharField(max_length=40, blank=True, help_text="Bank account or phone number")
    account_name = models.CharField(max_length=120, blank=True)
    swift_code = models.CharField("SWIFT code", max_length=20, blank=True)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    opening_date = models.DateField(help_text="The day the opening balance was counted")
    show_on_documents = models.BooleanField(default=True, help_text="Print under Payment Methods on invoices")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta:
        ordering = ("sort_order", "name")

    def __str__(self):
        return self.name
