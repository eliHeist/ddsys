from django.db import models

from apps.core.models import AbstractLine


class QuotationLine(AbstractLine):
    quotation = models.ForeignKey("billing.Quotation", on_delete=models.CASCADE, related_name="lines")

    class Meta(AbstractLine.Meta):
        pass
