from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from .models import CompanySettings, StaffProfile


class MoneyField(forms.DecimalField):
    """Accepts what an Alpine money mask produces: "1,250,000" or "1 250 000"."""

    def to_python(self, value):
        if isinstance(value, str):
            value = value.replace(",", "").replace(" ", "")
        return super().to_python(value)


def clean_number(text, default="0"):
    """Decimal from user text with thousands separators; raises InvalidOperation on junk."""
    return Decimal((text or "").replace(",", "").replace(" ", "") or default)


# The look of django-cotton-ui's form controls (<c-ui.input>, <c-ui.select.native>, <c-ui.textarea> at size "sm"),
# for plain Django widgets rendered with {{ field }} in core/form.html. Keep in step with the kit's templates.
KIT_CONTROL = ("block w-full rounded-control border border-ink-300 bg-[var(--color-input-bg)] text-sm text-ink-900 "
               "shadow-[var(--shadow-input)] placeholder:text-ink-400 focus-ring disabled:cursor-not-allowed "
               "disabled:opacity-50 dark:border-ink-700 dark:text-ink-100 dark:placeholder:text-ink-500")
KIT_WIDGET_CLASSES = {
    "input": f"{KIT_CONTROL} px-3 py-1.5",
    "select": f"{KIT_CONTROL} px-3 py-1.5",
    "textarea": f"{KIT_CONTROL} px-2.5 py-1.5",
    "checkbox": "size-4 accent-[var(--color-accent)]",
}


def kit_widget_class(widget):
    if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
        return KIT_WIDGET_CLASSES["checkbox"]
    if isinstance(widget, forms.Select):
        return KIT_WIDGET_CLASSES["select"]
    if isinstance(widget, forms.Textarea):
        return KIT_WIDGET_CLASSES["textarea"]
    return KIT_WIDGET_CLASSES["input"]


class Styled:
    """Gives every visible widget the kit's control styling, so forms rendered field by field match the
    <c-ui.*> components. Put it first in the bases: class StaffForm(Styled, forms.ModelForm)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():  # pyright: ignore[reportAttributeAccessIssue]
            if not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs.setdefault("class", kit_widget_class(field.widget))


class CompanySettingsForm(Styled, forms.ModelForm):
    class Meta:
        model = CompanySettings
        exclude = ("created_at", "updated_at")
        widgets = {
            "quotation_terms": forms.Textarea(attrs={"rows": 4}),
            "invoice_terms": forms.Textarea(attrs={"rows": 4}),
            "receipt_terms": forms.Textarea(attrs={"rows": 4}),
        }


class StaffEditForm(Styled, forms.ModelForm):
    class Meta:
        model = StaffProfile
        fields = ("role", "title", "phone", "is_active")


class StaffCreateForm(Styled, forms.Form):
    first_name = forms.CharField(max_length=25)
    last_name = forms.CharField(max_length=25, required=False)
    email = forms.EmailField()
    role = forms.ChoiceField(choices=StaffProfile.Role.choices, initial=StaffProfile.Role.STAFF)
    title = forms.CharField(max_length=80, required=False)
    phone = forms.CharField(max_length=30, required=False)
    password = forms.CharField(min_length=10, widget=forms.PasswordInput,
                               help_text="At least 10 characters. Ask them to change it after their first sign-in.")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Someone already signs in with this email.")
        return email
