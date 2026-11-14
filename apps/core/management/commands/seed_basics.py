from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import CompanySettings
from apps.finance.models import Account, ExpenseCategory

ACCOUNTS = [
    {"name": "Stanbic Bank", "kind": Account.Kind.BANK, "account_number": "9030020754582",
     "account_name": "DAKDOT CREATIONS LIMITED", "swift_code": "SBICUGKXXXX", "sort_order": 1},
    {"name": "MTN Mobile Money", "kind": Account.Kind.MOBILE_MONEY, "account_number": "+256 760 971269",
     "account_name": "ELIJAH ANGENGEUN", "sort_order": 2},
    {"name": "Cash", "kind": Account.Kind.CASH, "show_on_documents": False, "sort_order": 3},
]

CATEGORIES = ["Printing & production", "Transport", "Internet & data", "Software & subscriptions", "Hosting & domains",
              "Salaries & wages", "Rent & utilities", "Equipment", "Marketing", "Bank & mobile money charges",
              "Taxes & fees", "Other"]


class Command(BaseCommand):
    help = "Create the company settings, the Stanbic / MTN MoMo / Cash accounts and the expense categories (safe to re-run)."

    def handle(self, *args, **options):
        CompanySettings.load()
        today = timezone.localdate()
        for spec in ACCOUNTS:
            _, made = Account.objects.get_or_create(name=spec["name"], defaults={**spec, "opening_date": today})
            self.stdout.write(f"{'Created' if made else 'Kept'} account {spec['name']}")
        for name in CATEGORIES:
            ExpenseCategory.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS(
            "Done. Set each account's opening balance and date in the app (Money > Accounts) before recording payments."))
