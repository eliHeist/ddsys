from django.core.management.base import BaseCommand

from apps.core.crypto import new_key


class Command(BaseCommand):
    help = "Print a new key for SECRETS_KEY in dakdot/.env."

    def handle(self, *args, **options):
        self.stdout.write(new_key())
        self.stderr.write("Put it in dakdot/.env as SECRETS_KEY=... and keep a copy somewhere safe.")
