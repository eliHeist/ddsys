from django.db import models

from .base_models import TimeStampedModel

DEFAULT_INVOICE_TERMS = """A downpayment of 80% is required before the work commences.
Ownership of all design and assets created as part of this project will transfer to the client upon receipt of full payment.
This invoice covers the design and development services outlined in the project proposal date. Any additional work requested beyond the scope outlined in the proposal will be subject to additional charges."""

DEFAULT_RECEIPT_TERMS = """This receipt confirms payment received against the invoice referenced above.
Ownership of all design and assets transfers to the client upon receipt of full payment.
Please keep this receipt for your records. Payments are non-refundable once work has commenced."""

DEFAULT_QUOTATION_TERMS = """This quotation is valid for the period shown above.
A downpayment of 80% is required before the work commences.
Any additional work requested beyond the scope of this quotation will be subject to additional charges."""


class CompanySettings(TimeStampedModel):
    """The one row of company details printed on every document. Use CompanySettings.load()."""

    name = models.CharField(max_length=120, default="Dakdot Creations")
    legal_name = models.CharField(max_length=120, default="Dakdot Creations Limited")
    tagline = models.CharField(max_length=120, default="Digital Solutions. Design Excellence.")
    phone = models.CharField(max_length=40, default="0769345389")
    email = models.EmailField(default="connect@dakdot.com")
    address = models.CharField(max_length=200, default="Kampala-Uganda")
    tin = models.CharField("TIN", max_length=30, blank=True)
    logo = models.ImageField(upload_to="company/", blank=True, help_text="Printed at the top of documents")

    quotation_valid_days = models.PositiveSmallIntegerField(default=14)
    invoice_due_days = models.PositiveSmallIntegerField(default=14)
    quotation_terms = models.TextField(default=DEFAULT_QUOTATION_TERMS, help_text="One term per line")
    invoice_terms = models.TextField(default=DEFAULT_INVOICE_TERMS, help_text="One term per line")
    receipt_terms = models.TextField(default=DEFAULT_RECEIPT_TERMS, help_text="One term per line")
    receipt_thank_you = models.CharField(max_length=120, default="Thank you for your business.")

    class Meta:
        verbose_name = verbose_name_plural = "Company settings"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    async def aload(cls):
        obj, _ = await cls.objects.aget_or_create(pk=1)
        return obj

    @property
    def footer_line(self):
        return " | ".join(part for part in (self.name, self.address, self.phone, self.email) if part)
