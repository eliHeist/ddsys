from decimal import Decimal

from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AbstractLine(models.Model):
    """One row of a quotation or invoice: "Junior Kindergarten report, A3-A4, 5,000 x 18".

    A lump-sum row ("Binding: 50,000") has no price or quantity of its own: it keeps quantity 1 and the
    amount as the price, so totals add up the same way, and documents print "-" in those two columns.
    """

    description = models.CharField(max_length=255)
    note = models.CharField(max_length=255, blank=True, help_text='Small text under the description, e.g. "A3-A4"')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_lump_sum = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ("sort_order", "id")

    @property
    def amount(self):
        return (self.quantity * self.unit_price).quantize(Decimal("1.00"))

    @property
    def quantity_label(self):
        """"18", "2.5": the quantity as documents print it."""
        text = f"{self.quantity:f}"
        return text.rstrip("0").rstrip(".") if "." in text else text

    def __str__(self):
        return self.description
