from django.conf import settings
from django.db import models
from num2words import num2words
from simple_history.models import HistoricalRecords

from apps.core.mixins.numbering import NumberedMixin
from apps.core.models import TimeStampedModel


class Receipt(NumberedMixin, TimeStampedModel):
    """Money received from a client. Recording one also puts the money into a finance account, so a receipt
    always has a matching transaction (and a fee transaction when a charge was taken off on the way in).

    Two ways money comes in (billing.services.receipts):
    - a payment on an invoice (record_payment): `invoice` is set and the money pays it straight away;
    - a deposit (record_deposit): no invoice yet. The money is the client's credit until it is applied to an
      invoice. `quotation` or `project` say what it is for; credit tied to one is applied automatically when an
      invoice for it is issued.

    What a receipt paid is in its allocations (billing.Allocation); whatever is not allocated is credit. A payment
    bigger than its invoice's balance leaves the extra as credit too.

    The amounts the printed receipt shows (invoice total, previously paid) are kept as they were at the time, so
    reprinting an old receipt never changes it.
    """

    number_prefix = "RCT"

    class Status(models.TextChoices):
        VALID = "valid", "Valid"
        VOID = "void", "Void"

    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="receipts")
    invoice = models.ForeignKey("billing.Invoice", null=True, blank=True, on_delete=models.PROTECT, related_name="receipts",
                                help_text="The invoice it was paid against. Empty for a deposit")
    quotation = models.ForeignKey("billing.Quotation", null=True, blank=True, on_delete=models.PROTECT,
                                  related_name="deposits", help_text="Deposits: the quotation it is a deposit on")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.PROTECT,
                                related_name="receipts", help_text="The project it was paid for, if any")
    number = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VALID)
    date = models.DateField(help_text="The day the money was received; the number is made from it")
    amount = models.DecimalField(max_digits=14, decimal_places=2, help_text="What the client paid towards the invoice")
    fee = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                              help_text="Charge taken off on the way in (mobile money / bank); the client still gets credit for the full amount")
    account = models.ForeignKey("finance.Account", on_delete=models.PROTECT, related_name="receipts",
                                help_text="Where the money went: bank, mobile money or cash")
    reference = models.CharField(max_length=80, blank=True, help_text="Mobile money or bank transaction ID")
    received_from = models.CharField(max_length=150)
    being_payment_for = models.CharField(max_length=255)
    invoice_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    previously_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
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
    def net_received(self):
        """What actually landed in the account."""
        return self.amount - self.fee

    @property
    def is_deposit(self):
        return self.invoice_id is None

    @property
    def currency(self):
        return self.invoice.currency if self.invoice_id else settings.DEFAULT_CURRENCY

    @property
    def balance_due(self):
        """What the invoice still owed after this payment (as printed). Never below 0: extra became credit."""
        return max(self.invoice_total - self.previously_paid - self.amount, 0)

    @property
    def kept_as_credit(self):
        """The part of a payment on an invoice that was more than its balance, so stayed as credit."""
        return max(self.amount - (self.invoice_total - self.previously_paid), 0) if self.invoice_id else self.amount

    @property
    def purpose(self):
        """What it was for, in a few words: the invoice, or what the deposit is towards."""
        if self.invoice_id:
            return self.invoice.number
        if self.quotation_id:
            return f"Deposit on {self.quotation.label}"
        if self.project_id:
            return f"Deposit for {self.project.title}"
        return "Payment on account"

    @property
    def amount_in_words(self):
        """"Eight hundred thousand shillings only"."""
        words = num2words(int(self.amount), lang="en").replace(",", "").replace("-", " ")
        return f"{words[:1].upper()}{words[1:]} shillings only"
