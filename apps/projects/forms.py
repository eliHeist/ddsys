from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import MoneyField, Styled

from .models import Project


class ProjectForm(Styled, forms.ModelForm):
    budget = MoneyField(required=False, max_digits=14, decimal_places=2)

    class Meta:
        model = Project
        fields = ("client", "title", "status", "lead", "start_date", "due_date", "budget", "description")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = self.fields["client"].queryset.filter(is_active=True)
        self.fields["lead"].queryset = get_user_model().objects.filter(staff__is_active=True)
