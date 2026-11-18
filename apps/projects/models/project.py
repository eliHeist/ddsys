from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import TimeStampedModel


class Project(TimeStampedModel):
    """Something Dakdot works on or owns. Quotations, invoices, subscriptions, expenses and other income can hang
    off it, which is how its page shows what came in and what it cost. Three kinds:

    - CLIENT work: done for one client (`client` set); takes only that client's documents.
    - INTERNAL: Dakdot's own work (its website, this system); no client, usually only costs.
    - PRODUCT: a product Dakdot owns and sells (a SaaS). No client: its customers are clients with subscriptions
      and invoices on it. `code` is the product's stable key, which the product's own app will use to pull its
      records (subscribers, who has paid) through the API.
    """

    class Kind(models.TextChoices):
        CLIENT = "client", "Client work"
        INTERNAL = "internal", "Internal"
        PRODUCT = "product", "Our product"

    class Status(models.TextChoices):
        LEAD = "lead", "Lead"
        ACTIVE = "active", "Active"
        ON_HOLD = "on_hold", "On hold"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.CLIENT)
    client = models.ForeignKey("clients.Client", null=True, blank=True, on_delete=models.PROTECT, related_name="projects",
                               help_text="Only for client work")
    code = models.SlugField(max_length=40, unique=True, null=True, blank=True,
                            help_text="Products only: a short fixed key, e.g. dotscholar. The product's app uses it to fetch its records.")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    lead = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="led_projects", help_text="Who is in charge of this project")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    history = HistoricalRecords()

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.title} ({self.client or self.get_kind_display()})"

    def clean(self):
        if self.kind == self.Kind.CLIENT and not self.client_id:
            raise ValidationError({"client": "Client work needs a client. For Dakdot's own work choose Internal or Our product."})
        if self.kind != self.Kind.CLIENT and self.client_id:
            raise ValidationError({"client": "Internal projects and our products have no client. Leave it empty."})
        if self.kind == self.Kind.PRODUCT and not self.code:
            raise ValidationError({"code": "Give the product a short code, e.g. dotscholar."})
        if self.kind != self.Kind.PRODUCT:
            self.code = None

    @property
    def is_product(self):
        return self.kind == self.Kind.PRODUCT

    @property
    def is_internal(self):
        return self.kind == self.Kind.INTERNAL

    @property
    def owner_label(self):
        return self.client.name if self.client_id else f"Dakdot · {self.get_kind_display()}"

    @property
    def is_open(self):
        return self.status in (self.Status.LEAD, self.Status.ACTIVE, self.Status.ON_HOLD)
