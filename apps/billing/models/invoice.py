from decimal import Decimal

from django.db import models
from django.db.models import Sum
from simple_history.models import HistoricalRecords

from .base_document import BillingDocument


class Invoice(BillingDocument):
    number_prefix = "INV"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PARTIAL = "partial", "Partially paid"
        PAID = "paid", "Paid"
        VOID = "void", "Void"

    OPEN = (Status.ISSUED, Status.PARTIAL)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    quotation = models.ForeignKey("billing.Quotation", null=True, blank=True, on_delete=models.PROTECT,
                                  related_name="invoices")
    due_date = models.DateField(null=True, blank=True)
    subscription = models.ForeignKey("billing.Subscription", null=True, blank=True, on_delete=models.PROTECT,
                                     related_name="invoices")
    period_start = models.DateField(null=True, blank=True, help_text="Subscriptions: the period this invoice pays for")
    period_end = models.DateField(null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta(BillingDocument.Meta):
        constraints = (
            models.UniqueConstraint(fields=("number",), condition=~models.Q(number=""), name="invoice_unique_number"),
        )

    @property
    def balance(self):
        return self.total - self.amount_paid

    @property
    def is_open(self):
        return self.status in self.OPEN

    def refresh_payments(self):
        """Paid amount and status from the allocations of valid receipts (payments on it and credit applied to it).
        Call inside the transaction that changed them."""
        self.amount_paid = (self.allocations.filter(receipt__status="valid").aggregate(s=Sum("amount"))["s"]  # pyright: ignore[reportAttributeAccessIssue]
                            or Decimal(0))
        if self.status not in (self.Status.DRAFT, self.Status.VOID):
            if self.amount_paid >= self.total:
                self.status = self.Status.PAID
            elif self.amount_paid > 0:
                self.status = self.Status.PARTIAL
            else:
                self.status = self.Status.ISSUED
        self.save(update_fields=["amount_paid", "status", "updated_at"])
