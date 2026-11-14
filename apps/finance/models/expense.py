from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import TimeStampedModel


class Expense(TimeStampedModel):
    """Money spent: printing, transport, data, salaries... Linking it to a project counts it in that
    project's costs. Recording one takes the money out of the chosen account."""

    class Status(models.TextChoices):
        VALID = "valid", "Valid"
        VOID = "void", "Void"

    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    account = models.ForeignKey("finance.Account", on_delete=models.PROTECT, related_name="expenses",
                                help_text="Where the money was paid from")
    category = models.ForeignKey("finance.ExpenseCategory", on_delete=models.PROTECT, related_name="expenses")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.PROTECT, related_name="expenses")
    payee = models.CharField(max_length=150, blank=True, help_text="Who was paid")
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=80, blank=True, help_text="Receipt, mobile money or bank transaction ID")
    attachment = models.FileField(upload_to="expenses/%Y/%m/", blank=True, help_text="Photo or PDF of the receipt")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.VALID)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta:
        ordering = ("-date", "-created_at")

    def __str__(self):
        return self.description
