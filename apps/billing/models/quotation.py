from django.db import models
from simple_history.models import HistoricalRecords

from .base_document import BillingDocument


class Quotation(BillingDocument):
    number_prefix = "QUO"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        VOID = "void", "Void"

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    valid_until = models.DateField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta(BillingDocument.Meta):
        constraints = (
            models.UniqueConstraint(fields=("number",), condition=~models.Q(number=""), name="quotation_unique_number"),
        )

    @property
    def invoice(self):
        """The live invoice made from this quotation, if any (prefetch `invoices` to avoid a query)."""
        return next((i for i in self.invoices.all() if i.status != i.Status.VOID), None)  # pyright: ignore[reportAttributeAccessIssue]
