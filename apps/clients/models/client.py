from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import TimeStampedModel


class Client(TimeStampedModel):
    """A school, business or person Dakdot works for. Its name is what documents print after "Invoice To"."""

    name = models.CharField(max_length=150, unique=True)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=200, blank=True)
    tin = models.CharField("TIN", max_length=30, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name
