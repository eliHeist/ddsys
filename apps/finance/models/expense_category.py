from django.db import models


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "expense categories"

    def __str__(self):
        return self.name
