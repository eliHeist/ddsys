from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.clients.models import Client
from apps.core.forms import MoneyField, Styled, clean_number
from apps.billing.models import Quotation, Subscription
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
    fee = MoneyField(max_digits=14, decimal_places=2, required=False)
    reference = forms.CharField(max_length=80, required=False)
    being_payment_for = forms.CharField(max_length=255, required=False)


class DepositForm(PaymentForm):
    quotation = forms.ModelChoiceField(queryset=Quotation.objects.all(), required=False)
    project = forms.ModelChoiceField(queryset=Project.objects.all(), required=False)
    received_from = forms.CharField(max_length=150, required=False)


class ApplyCreditForm(forms.Form):
    amount = MoneyField(max_digits=14, decimal_places=2, min_value=Decimal(1), required=False)


def _money_fields(accounts, amount=""):
    """Amount, date, account, fee and transaction ID: what every way of receiving money asks."""
    return [
        {"name": "amount", "label": "Amount received", "type": "money", "value": amount, "required": True},
        {"name": "date", "label": "Date received", "type": "date", "value": timezone.localdate().isoformat(), "required": True},
        {"name": "account", "label": "Received into", "type": "select", "required": True,
         "value": accounts[0].pk if accounts else "", "options": [[a.pk, a.name] for a in accounts]},
        {"name": "fee", "label": "Fee taken off (if any)", "type": "money", "value": "0"},
        {"name": "reference", "label": "Transaction ID (mobile money / bank)", "type": "text", "value": ""},
    ]


def deposit_dialog(client, accounts, *, quotations=(), projects=(), quotation=None):
    """Recording money that came before its invoice (on the client's or a quotation's page)."""
    from django.urls import reverse
    fields = _money_fields(accounts)
    fields.append({"name": "quotation", "label": "Deposit on quotation", "type": "select",
                   "value": quotation.pk if quotation else "",
                   "options": [["", "None"]] + [[q.pk, f"{q.number} · {q.total:,.0f}"] for q in quotations]})
    if projects:
        fields.append({"name": "project", "label": "Or for project", "type": "select", "value": "",
                       "options": [["", "None"]] + [[p.pk, p.title] for p in projects]})
    fields.append({"name": "being_payment_for", "label": "Being payment for", "type": "textarea",
                   "value": f"Deposit on quotation {quotation.number}." if quotation else ""})
    return {
        "title": f"Record a deposit from {client.name}",
        "message": "Money paid before its invoice. It goes into the account now and stays as the client's credit. "
                   "Linked to a quotation or project, it pays that invoice automatically when it is issued.",
        "url": reverse("billing:deposit-new", args=[client.pk]), "submit": "Record deposit", "fields": fields,
    }


def apply_credit_dialog(invoice, credit):
    from django.urls import reverse
    usable = min(credit, invoice.balance)
    return {
        "title": f"Apply credit to {invoice.number}",
        "message": f"{invoice.client} has {invoice.currency} {credit:,.0f} on account; the balance due is "
                   f"{invoice.currency} {invoice.balance:,.0f}. The oldest credit is used first. No money moves: it is already in.",
        "url": reverse("billing:invoice-apply-credit", args=[invoice.pk]), "submit": "Apply credit",
        "fields": [{"name": "amount", "label": "Amount to apply", "type": "money", "value": f"{usable:,.0f}", "required": True}],
    }


def receipt_apply_dialog(receipt, open_invoices):
    from django.urls import reverse
    return {
        "title": f"Apply {receipt.number} to an invoice",
        "message": f"{receipt.currency} {receipt.credit:,.0f} of this receipt is credit. Leave the amount empty to use "
                   "as much as the invoice needs.",
        "url": reverse("billing:receipt-apply", args=[receipt.pk]), "submit": "Apply",
        "fields": [
            {"name": "invoice", "label": "Invoice", "type": "select", "required": True,
             "value": open_invoices[0].pk if open_invoices else "",
             "options": [[i.pk, f"{i.number} · owes {i.balance:,.0f}"] for i in open_invoices]},
            {"name": "amount", "label": "Amount (optional)", "type": "money", "value": ""},
        ],
    }


def payment_dialog(invoice, accounts):
    """The action dialog's settings for recording a payment (core/_action_dialog.html)."""
    from django.urls import reverse
    return {
        "title": f"Record a payment on {invoice.number}",
        "message": f"Balance due: {invoice.currency} {invoice.balance:,.0f}. The receipt is numbered from the payment date. "
                   "Anything above the balance is kept as the client's credit.",
        "url": reverse("billing:invoice-pay", args=[invoice.pk]),
        "submit": "Record payment",
        "fields": _money_fields(accounts, f"{invoice.balance:,.0f}") + [
            {"name": "being_payment_for", "label": "Being payment for", "type": "textarea",
             "value": f"Payment on invoice {invoice.number}."},
        ],
    }


def void_dialog(title, url, what):
    return {"title": title, "message": f"{what} keeps its number and stays on record, marked void.", "url": url,
            "submit": "Void", "danger": True,
            "fields": [{"name": "reason", "label": "Why?", "type": "textarea", "value": "", "required": True}]}


class SubscriptionForm(Styled, forms.Form):
    """A subscription's header. Its lines come from the line editor (parse_lines)."""

    client = forms.ModelChoiceField(queryset=Client.objects.filter(is_active=True))
    project = forms.ModelChoiceField(
        queryset=Project.objects.select_related("client").exclude(kind=Project.Kind.INTERNAL), required=False,
        label="Product or project", help_text="The product being paid for, or the client project for a service")
    title = forms.CharField(max_length=150, help_text='e.g. "School system - Standard plan" or "Website hosting"')
    interval_months = forms.TypedChoiceField(label="Bill", coerce=int, choices=Subscription.Interval.choices)
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), help_text="The first invoice is made on this day")
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}),
                               help_text="Leave empty to continue until ended")
    due_days = forms.IntegerField(min_value=0, max_value=90, initial=7, label="Days to pay each invoice")
    auto_issue = forms.BooleanField(required=False, label="Issue invoices straight away",
                                    help_text="Otherwise each invoice waits as a draft for you to check and issue")
    external_ref = forms.CharField(max_length=80, required=False, label="ID in the product",
                                   help_text="The client's account or tenant ID in the product's app (for the API)")
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), help_text="Printed on each invoice")
