from django import forms

from apps.core.forms import Styled

from .models import Client


class ClientForm(Styled, forms.ModelForm):
    class Meta:
        model = Client
        fields = ("name", "contact_person", "phone", "email", "address", "tin", "notes", "is_active")
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
