from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Transfer(TimeStampedModel):
    """Money moved between Dakdot's own accounts, e.g. mobile money withdrawn to the bank. It is neither
    income nor spending: it makes two transactions, out of one account and into the other. A fee charged on
    the way (`fee`) is a third transaction out of the sending account."""

    class Status(models.TextChoices):
        VALID = "valid", "Valid"
        VOID = "void", "Void"

    date = models.DateField()
    from_account = models.ForeignKey("finance.Account", on_delete=models.PROTECT, related_name="transfers_out")
    to_account = models.ForeignKey("finance.Account", on_delete=models.PROTECT, related_name="transfers_in")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    fee = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    note = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VALID)
    voided_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ("-date", "-created_at")

    def __str__(self):
        return f"{self.from_account} → {self.to_account}: {self.amount}"
