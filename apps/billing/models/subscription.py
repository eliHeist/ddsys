from decimal import Decimal

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.dates import period_end
from apps.core.models import TimeStampedModel


class Subscription(TimeStampedModel):
    """A client paying regularly: for one of Dakdot's products (a SaaS plan), or for a service such as hosting
    or a retainer. Every period it makes an invoice from its lines (billing.services.subscriptions), covering
    `next_invoice_date` up to the day before the next one, and moves `next_invoice_date` on.

    `external_ref` is the client's ID inside the product (a tenant or school slug), so the product's app can
    match its customers to these records when it pulls them through the API.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        ENDED = "ended", "Ended"

    class Interval(models.IntegerChoices):
        MONTHLY = 1, "Monthly"
        QUARTERLY = 3, "Every 3 months"
        HALF_YEARLY = 6, "Every 6 months"
        YEARLY = 12, "Yearly"

    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="subscriptions")
    project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.PROTECT,
                                related_name="subscriptions", help_text="Usually the product being paid for")
    title = models.CharField(max_length=150, help_text='e.g. "School system - Standard plan" or "Website hosting"')
    interval_months = models.PositiveSmallIntegerField("Bill", choices=Interval.choices, default=Interval.MONTHLY)
    start_date = models.DateField()
    next_invoice_date = models.DateField(help_text="The day the next invoice is made; it covers the period from then")
    end_date = models.DateField(null=True, blank=True, help_text="Leave empty to continue until ended")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    auto_issue = models.BooleanField(default=False, help_text="Issue each invoice straight away instead of leaving a draft")
    due_days = models.PositiveSmallIntegerField(default=7, help_text="Days the client has to pay each invoice")
    currency = models.CharField(max_length=3, default="UGX")
    external_ref = models.CharField("ID in the product", max_length=80, blank=True,
                                    help_text="The client's account or tenant ID in the product's app")
    notes = models.TextField(blank=True, help_text="Printed on each invoice")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    history = HistoricalRecords(excluded_fields=["updated_at"])

    class Meta:
        ordering = ("status", "next_invoice_date")

    def __str__(self):
        return f"{self.title} · {self.client}"

    @property
    def amount(self):
        """What each invoice comes to (prefetch `lines`)."""
        return sum((line.amount for line in self.lines.all()), Decimal(0))  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def total(self):  # same name as on invoices, so shared templates can show it
        return self.amount

    @property
    def monthly_value(self):
        return (self.amount / self.interval_months).quantize(Decimal("1"))

    @property
    def next_period_end(self):
        return period_end(self.next_invoice_date, self.interval_months)
