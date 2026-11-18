from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


class Allocation(models.Model):
    """Part (or all) of a receipt used to pay an invoice.

    A payment on an invoice gets one straight away. A deposit gets them later, when its credit is applied, and
    one deposit can pay several invoices. An invoice's paid amount is the sum of its allocations from valid
    receipts (Invoice.refresh_payments), and a receipt's credit is what it has not allocated. No money moves:
    it moved when the receipt was recorded.
    """

    receipt = models.ForeignKey("billing.Receipt", on_delete=models.PROTECT, related_name="allocations")
    invoice = models.ForeignKey("billing.Invoice", on_delete=models.PROTECT, related_name="allocations")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField(help_text="When it was applied")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ("date", "id")
        constraints = (models.CheckConstraint(condition=models.Q(amount__gt=0), name="allocation_amount_positive"),)

    def __str__(self):
        return f"{self.amount:,.0f} of {self.receipt} to {self.invoice}"

    @property
    def is_from_deposit(self):
        """Credit applied, rather than a payment made on this invoice."""
        return self.receipt.invoice_id != self.invoice_id
