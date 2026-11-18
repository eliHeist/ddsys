from datetime import date

from django.core.management.base import BaseCommand

from apps.billing.services.subscriptions import bill_due_subscriptions


class Command(BaseCommand):
    help = "Make the invoices for subscriptions that have fallen due. Run once a day (cron / scheduled task)."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=date.fromisoformat, help="Bill as if today were this date (YYYY-MM-DD)")

    def handle(self, *args, **options):
        made, errors = bill_due_subscriptions(options.get("date"))
        for invoice in made:
            self.stdout.write(f"{invoice.label}: {invoice.client} · {invoice.subscription.title} · {invoice.total:,.0f}")
        for pk, message in errors:
            self.stderr.write(self.style.ERROR(f"Subscription {pk}: {message}"))
        self.stdout.write(self.style.SUCCESS(f"{len(made)} invoice(s) made, {len(errors)} problem(s)."))
