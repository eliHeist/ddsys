from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.mixins.numbering import NumberedMixin
from apps.core.models import TimeStampedModel


class BillingDocument(NumberedMixin, TimeStampedModel):
    """What quotations and invoices share: a client, dated lines and a total.

    A draft has no number and no date: both are set when it is issued, and the number is made from that
    date. Issued documents are frozen; a mistake is fixed by voiding and issuing a new one.
    """

    DRAFT = "draft"
    VOID = "void"

    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="%(class)ss")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.PROTECT,
                                related_name="%(class)ss")
    number = models.CharField(max_length=20, blank=True)
    date = models.DateField(null=True, blank=True, help_text="Issue date, set when issued")
    currency = models.CharField(max_length=3, default="UGX")
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True, help_text="Printed on the document")
    terms = models.TextField(blank=True, help_text="One term per line")
    issued_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        abstract = True
        ordering = ("-date", "-created_at")

    @property
    def number_ready(self):
        return self.status not in (self.DRAFT, self.VOID) and self.date is not None  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def is_draft(self):
        return self.status == self.DRAFT  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def is_void(self):
        return self.status == self.VOID  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def kind(self):
        return self._meta.verbose_name.title()

    @property
    def label(self):
        return self.number or f"Draft {self._meta.verbose_name}"

    @property
    def term_list(self):
        return [line.strip() for line in self.terms.splitlines() if line.strip()]

    def recalculate(self):
        """Total from the lines. Call after the lines change (drafts only)."""
        self.total = sum((line.amount for line in self.lines.all()), Decimal(0))  # pyright: ignore[reportAttributeAccessIssue]
        self.save(update_fields=["total", "updated_at"])

    def __str__(self):
        return self.label
