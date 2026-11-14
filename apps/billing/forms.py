from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.clients.models import Client
from apps.core.forms import MoneyField, Styled, clean_number
from apps.finance.models import Account
from apps.projects.models import Project


def parse_lines(post):
    """Line specs from the line editor's repeated fields (billing/partials/_line_editor.html)."""
    rows = zip(post.getlist("description"), post.getlist("note"), post.getlist("quantity"),
               post.getlist("unit_price"), post.getlist("lump_sum"))
    specs = []
    for description, note, quantity, unit_price, lump_sum in rows:
        if not description.strip() and not unit_price.strip():
            continue  # an empty row left at the end
        try:
            specs.append({"description": description, "note": note, "quantity": clean_number(quantity, "1"),
                          "unit_price": clean_number(unit_price), "is_lump_sum": lump_sum == "1"})
        except InvalidOperation:
            raise ValidationError(f'"{description or "A line"}": the quantity and price must be numbers.')
    return specs


def lines_for_editor(lines):
    """Saved lines in the shape the line editor starts from."""
    return [{"description": l.description, "note": l.note, "quantity": l.quantity_label,
             "unit_price": f"{l.unit_price:,.0f}", "lump_sum": l.is_lump_sum} for l in lines]


class DocumentForm(Styled, forms.Form):
    """The header of a quotation or invoice: who it is for and what it says besides the lines."""

    client = forms.ModelChoiceField(queryset=Client.objects.filter(is_active=True))
    project = forms.ModelChoiceField(queryset=Project.objects.select_related("client"), required=False,
                                     help_text="Optional. Must belong to the client.")
    date_limit = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    terms = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}), help_text="One term per line")

    def __init__(self, *args, date_label="Due date", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date_limit"].label = date_label
        self.fields["date_limit"].help_text = "Left empty, it is set from the company settings when issued."


class PaymentForm(forms.Form):
    amount = MoneyField(max_digits=14, decimal_places=2, min_value=Decimal(1))
    date = forms.DateField()
    account = forms.ModelChoiceField(queryset=Account.objects.filter(is_active=True))
    reference = forms.CharField(max_length=80, required=False)
    being_payment_for = forms.CharField(max_length=255, required=False)


def payment_dialog(invoice, accounts):
    """The action dialog's settings for recording a payment (core/_action_dialog.html)."""
    from django.urls import reverse
    return {
        "title": f"Record a payment on {invoice.number}",
        "message": f"Balance due: {invoice.currency} {invoice.balance:,.0f}. The receipt is numbered from the payment date.",
        "url": reverse("billing:invoice-pay", args=[invoice.pk]),
        "submit": "Record payment",
        "fields": [
            {"name": "amount", "label": "Amount received", "type": "money", "value": f"{invoice.balance:,.0f}", "required": True},
            {"name": "date", "label": "Date received", "type": "date", "value": timezone.localdate().isoformat(), "required": True},
            {"name": "account", "label": "Received into", "type": "select", "required": True,
             "value": accounts[0].pk if accounts else "", "options": [[a.pk, a.name] for a in accounts]},
            {"name": "reference", "label": "Transaction ID (mobile money / bank)", "type": "text", "value": ""},
            {"name": "being_payment_for", "label": "Being payment for", "type": "textarea",
             "value": f"Payment on invoice {invoice.number}."},
        ],
    }


def void_dialog(title, url, what):
    return {"title": title, "message": f"{what} keeps its number and stays on record, marked void.", "url": url,
            "submit": "Void", "danger": True,
            "fields": [{"name": "reason", "label": "Why?", "type": "textarea", "value": "", "required": True}]}
