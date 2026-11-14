from django import forms

from apps.core.forms import MoneyField, Styled
from apps.projects.models import Project

from .models import Account, ExpenseCategory, Transaction


class AccountForm(Styled, forms.ModelForm):
    opening_balance = MoneyField(max_digits=14, decimal_places=2, initial=0)

    class Meta:
        model = Account
        fields = ("name", "kind", "account_number", "account_name", "swift_code", "opening_balance", "opening_date",
                  "show_on_documents", "is_active", "sort_order")
        widgets = {"opening_date": forms.DateInput(attrs={"type": "date"})}


class ExpenseForm(Styled, forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    amount = MoneyField(max_digits=14, decimal_places=2)
    account = forms.ModelChoiceField(queryset=Account.objects.filter(is_active=True), label="Paid from")
    category = forms.ModelChoiceField(queryset=ExpenseCategory.objects.filter(is_active=True))
    description = forms.CharField(max_length=255)
    payee = forms.CharField(max_length=150, required=False, label="Paid to")
    project = forms.ModelChoiceField(queryset=Project.objects.select_related("client"), required=False,
                                     help_text="Counts in that project's costs")
    reference = forms.CharField(max_length=80, required=False, label="Transaction ID / receipt no.")
    attachment = forms.FileField(required=False, help_text="Photo or PDF of the receipt")


class TransferForm(Styled, forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    from_account = forms.ModelChoiceField(queryset=Account.objects.filter(is_active=True), label="From")
    to_account = forms.ModelChoiceField(queryset=Account.objects.filter(is_active=True), label="To")
    amount = MoneyField(max_digits=14, decimal_places=2)
    fee = MoneyField(max_digits=14, decimal_places=2, required=False, initial=0, help_text="Withdrawal or bank charge")
    note = forms.CharField(max_length=255, required=False)
    reference = forms.CharField(max_length=80, required=False)


class OtherIncomeForm(Styled, forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    account = forms.ModelChoiceField(queryset=Account.objects.filter(is_active=True), label="Received into")
    amount = MoneyField(max_digits=14, decimal_places=2)
    description = forms.CharField(max_length=255, help_text="What the money is, e.g. capital from directors")
    reference = forms.CharField(max_length=80, required=False)


class AdjustmentForm(Styled, forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    account = forms.ModelChoiceField(queryset=Account.objects.all())
    direction = forms.ChoiceField(choices=Transaction.Direction.choices)
    amount = MoneyField(max_digits=14, decimal_places=2)
    reason = forms.CharField(max_length=200, help_text="e.g. Bank charges for October, cash count was short")
