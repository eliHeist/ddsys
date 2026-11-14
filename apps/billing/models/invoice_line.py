from django.db import models

from apps.core.models import AbstractLine


class InvoiceLine(AbstractLine):
    invoice = models.ForeignKey("billing.Invoice", on_delete=models.CASCADE, related_name="lines")

    class Meta(AbstractLine.Meta):
        pass
