from django import forms

from apps.core.forms import MoneyField, Styled
from apps.core.models import StaffProfile
from apps.projects.models import Project

from .models import Account, ExpenseCategory, Transaction


class AccountForm(Styled, forms.ModelForm):
    opening_balance = MoneyField(max_digits=14, decimal_places=2, initial=0)

    class Meta:
        model = Account
        fields = ("name", "kind", "account_number", "account_name", "swift_code", "opening_balance", "opening_date",
                  "show_on_documents", "is_active", "sort_order")
        widgets = {"opening_date": forms.DateInput(attrs={"type": "date"})}


def our_people():
    """Directors and active staff, directors first: anyone who can lend to the company or pay its costs."""
    return StaffProfile.objects.filter(is_active=True).select_related("user").order_by("-is_director", "user__first_name")


class PersonChoice(forms.ModelChoiceField):
    def label_from_instance(self, profile):
        return f"{profile.name} (director)" if profile.is_director else profile.name


class ExpenseForm(Styled, forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    amount = MoneyField(max_digits=14, decimal_places=2)
    fee = MoneyField(max_digits=14, decimal_places=2, required=False, initial=0,
                     help_text="Mobile money or bank charge for paying it, if any. Recorded as its own line.")
    account = forms.ModelChoiceField(queryset=Account.objects.filter(is_active=True), label="Paid from", required=False,
                                     empty_label="No account: someone paid it all themselves")
    paid_by = PersonChoice(queryset=StaffProfile.objects.none(), required=False,
                           label="Paid (all or part) by someone from their own money",
                           help_text="A director or any staff member. What they paid is owed back to them.")
    paid_by_amount = MoneyField(max_digits=14, decimal_places=2, required=False, label="How much they paid",
                                help_text="Only if they topped up: the account above paid the rest. Empty: they paid it all.")
    must_repay = forms.BooleanField(required=False, initial=True, label="They are to be paid back",
                                    help_text="Untick if a director is putting it in as capital.")
    category = forms.ModelChoiceField(queryset=ExpenseCategory.objects.filter(is_active=True))
    description = forms.CharField(max_length=255)
    payee = forms.CharField(max_length=150, required=False, label="Paid to")
    project = forms.ModelChoiceField(queryset=Project.objects.select_related("client"), required=False,
                                     help_text="Counts in that project's costs")
    reference = forms.CharField(max_length=80, required=False, label="Transaction ID / receipt no.")
    attachment = forms.FileField(required=False, help_text="Photo or PDF of the receipt")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["paid_by"].queryset = our_people()
        self.fields["paid_by"].empty_label = "Nobody: the account above paid it all"
        self.order_fields(["date", "amount", "fee", "account", "paid_by", "paid_by_amount", "must_repay"])

    def clean(self):
        data = super().clean()
        if not data.get("account") and not data.get("paid_by"):
            raise forms.ValidationError("Choose the account it was paid from, or who paid it themselves.")
        if data.get("paid_by_amount") and not data.get("paid_by"):
            raise forms.ValidationError("Choose who paid that part from their own money.")
        return data


class LoanForm(Styled, forms.Form):
    person = PersonChoice(queryset=StaffProfile.objects.none(), required=False, label="From one of our people",
                          empty_label="Someone outside (type the name)", help_text="A director or any staff member")
    lender_name = forms.CharField(max_length=150, required=False, label="Or the lender's name",
                                  help_text="Someone outside the company: a person, a bank, a SACCO...")
    amount = MoneyField(max_digits=14, decimal_places=2)
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    account = forms.ModelChoiceField(queryset=Account.objects.filter(is_active=True), label="Received into")
    must_repay = forms.BooleanField(required=False, initial=True, label="Must be refunded",
                                    help_text="Untick if the company does not pay it back (a gift, or capital put in)")
    purpose = forms.CharField(max_length=255, label="What it is for")
    reference = forms.CharField(max_length=80, required=False, label="Transaction ID / reference")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["person"].queryset = our_people()


class RepaymentForm(forms.Form):
    amount = MoneyField(max_digits=14, decimal_places=2)
    date = forms.DateField()
    account = forms.ModelChoiceField(queryset=Account.objects.filter(is_active=True))
    fee = MoneyField(max_digits=14, decimal_places=2, required=False)
    reference = forms.CharField(max_length=80, required=False)
    note = forms.CharField(max_length=255, required=False)


def repay_dialog(loan, accounts):
    from django.urls import reverse
    from django.utils import timezone
    verb = "Reimburse" if loan.paid_costs_directly else "Repay"
    return {
        "title": f"{verb} {loan.lender_name}",
        "message": f"Still owed: {loan.owed:,.0f}. Pay it all, or part now and the rest later.",
        "url": reverse("finance:loan-repay", args=[loan.pk]), "submit": f"Record {'reimbursement' if verb == 'Reimburse' else 'repayment'}",
        "fields": [
            {"name": "amount", "label": "Amount paid back", "type": "money", "value": f"{loan.owed:,.0f}", "required": True},
            {"name": "date", "label": "Date paid", "type": "date", "value": timezone.localdate().isoformat(), "required": True},
            {"name": "account", "label": "Paid from", "type": "select", "required": True,
             "value": accounts[0].pk if accounts else "", "options": [[a.pk, a.name] for a in accounts]},
            {"name": "fee", "label": "Fee for sending it (if any)", "type": "money", "value": "0"},
            {"name": "reference", "label": "Transaction ID", "type": "text", "value": ""},
            {"name": "note", "label": "Note", "type": "text", "value": ""},
        ],
    }


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
    project = forms.ModelChoiceField(queryset=Project.objects.select_related("client"), required=False,
                                     help_text="The product or project it was earned on, if any")
    reference = forms.CharField(max_length=80, required=False)


class AdjustmentForm(Styled, forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    account = forms.ModelChoiceField(queryset=Account.objects.all())
    direction = forms.ChoiceField(choices=Transaction.Direction.choices)
    amount = MoneyField(max_digits=14, decimal_places=2)
    reason = forms.CharField(max_length=200, help_text="e.g. Bank charges for October, cash count was short")
