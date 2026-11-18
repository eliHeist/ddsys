from django.db import models

from apps.core.models import AbstractLine


class SubscriptionLine(AbstractLine):
    """A line copied onto every invoice the subscription makes."""

    subscription = models.ForeignKey("billing.Subscription", on_delete=models.CASCADE, related_name="lines")

    class Meta(AbstractLine.Meta):
        pass
