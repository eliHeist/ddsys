from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import KIT_WIDGET_CLASSES, Styled

from .models import Project, ProjectSecret


class ProjectForm(Styled, forms.ModelForm):
    class Meta:
        model = Project
        fields = ("kind", "title", "code", "client", "status", "lead", "start_date", "due_date", "description")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = self.fields["client"].queryset.filter(is_active=True)
        self.fields["client"].empty_label = "None (Dakdot's own work)"
        self.fields["lead"].queryset = get_user_model().objects.filter(staff__is_active=True)


class SecretForm(Styled, forms.ModelForm):
    """Add or change a project secret. The labels follow the kind: a variable has a name and a value, a login has
    a username, a password and a sign-in link. When editing, an empty value keeps the saved one."""

    value = forms.CharField(strip=False)

    class Meta:
        model = ProjectSecret
        fields = ("title", "name", "value", "link")

    def __init__(self, *args, project, kind, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.project, self.kind, self.user = project, kind, user
        editing = self.instance.pk is not None
        f = self.fields

        if kind == ProjectSecret.Kind.LOGIN:
            f["title"].help_text = "What the account is for, e.g. Django admin, cPanel, Google Workspace"
            f["name"].label, f["name"].help_text = "Username or email", ""
            f["value"].label = "Password"
            f["value"].widget = forms.PasswordInput(attrs={"autocomplete": "new-password", "class": KIT_WIDGET_CLASSES["input"]})
            f["link"].label, f["link"].help_text = "Sign-in link", "Where you sign in, e.g. https://example.com/admin/"
        else:
            f["title"].help_text = "What it is, e.g. Stripe live secret key"
            f["name"].label, f["name"].help_text = "Variable name", "As it goes in a .env file, e.g. STRIPE_SECRET_KEY"
            f["name"].widget.attrs.update({"class": f'{KIT_WIDGET_CLASSES["input"]} font-mono', "spellcheck": "false"})
            f["value"].widget = forms.Textarea(attrs={"rows": 3, "spellcheck": "false", "autocomplete": "off",
                                                      "class": f'{KIT_WIDGET_CLASSES["textarea"]} font-mono'})
            del f["link"]

        if editing:
            f["value"].required = False
            f["value"].help_text = "Leave empty to keep the saved one."

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if self.kind == ProjectSecret.Kind.VARIABLE:
            taken = ProjectSecret.objects.filter(project=self.project, kind=self.kind, name=name).exclude(pk=self.instance.pk)
            if taken.exists():
                raise forms.ValidationError("This project already has a variable with this name.")
        return name

    def save(self, commit=True):
        secret = super().save(commit=False)
        if secret.pk is None:
            secret.project, secret.kind, secret.created_by = self.project, self.kind, self.user
        secret.updated_by = self.user
        if self.cleaned_data["value"]:
            secret.value = self.cleaned_data["value"]
        if commit:
            secret.save()
        return secret
