from django.conf import settings
from django.db import models
from num2words import num2words
from simple_history.models import HistoricalRecords

from apps.core.mixins.numbering import NumberedMixin
from apps.core.models import TimeStampedModel


class Receipt(NumberedMixin, TimeStampedModel):
    """Money received against an invoice. Recording one (billing.services.receipts.record_payment) also puts
    the money into a finance account, so a receipt always has a matching transaction.

    The amounts the printed receipt shows (invoice total, previously paid, balance) are kept as they were at the
    time, so reprinting an old receipt never changes it.
    """

    number_prefix = "RCT"

    class Status(models.TextChoices):
        VALID = "valid", "Valid"
        VOID = "void", "Void"

    invoice = models.ForeignKey("billing.Invoice", on_delete=models.PROTECT, related_name="receipts")
    number = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VALID)
    date = models.DateField(help_text="The day the money was received; the number is made from it")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    account = models.ForeignKey("finance.Account", on_delete=models.PROTECT, related_name="receipts",
                                help_text="Where the money went: bank, mobile money or cash")
    reference = models.CharField(max_length=80, blank=True, help_text="Mobile money or bank transaction ID")
    received_from = models.CharField(max_length=150)
    being_payment_for = models.CharField(max_length=255)
    invoice_total = models.DecimalField(max_digits=14, decimal_places=2)
    previously_paid = models.DecimalField(max_digits=14, decimal_places=2)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True)

    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta:
        ordering = ("-date", "-created_at")
        constraints = (
            models.UniqueConstraint(fields=("number",), condition=~models.Q(number=""), name="receipt_unique_number"),
        )

    def __str__(self):
        return self.number or "Receipt"

    @property
    def label(self):
        return self.number

    @property
    def balance_due(self):
        return self.invoice_total - self.previously_paid - self.amount

    @property
    def amount_in_words(self):
        """"Eight hundred thousand shillings only"."""
        words = num2words(int(self.amount), lang="en").replace(",", "").replace("-", " ")
        return f"{words[:1].upper()}{words[1:]} shillings only"
