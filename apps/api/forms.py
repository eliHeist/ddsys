from django import forms

from apps.core.forms import Styled
from apps.projects.models import Project


class ApiKeyForm(Styled, forms.Form):
    name = forms.CharField(max_length=80, help_text='Where it will be used, e.g. "DotScholar production server"')
    product = forms.ModelChoiceField(queryset=Project.objects.filter(kind=Project.Kind.PRODUCT),
                                     help_text="The key can only read this product's records")
