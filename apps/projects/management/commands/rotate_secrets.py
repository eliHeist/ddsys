from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.crypto import reencrypt
from apps.projects.models import ProjectSecret


class Command(BaseCommand):
    help = ("Re-encrypt every project secret (and its history) with the first key in SECRETS_KEY. "
            "Run after putting a new key in front: SECRETS_KEY=new,old. Then remove the old key.")

    @transaction.atomic
    def handle(self, *args, **options):
        count = 0
        for model in (ProjectSecret, ProjectSecret.history.model):
            for pk, token in model.objects.exclude(encrypted_value="").values_list("pk", "encrypted_value"):
                # update() rather than save(): no new history rows, updated_at unchanged
                model.objects.filter(pk=pk).update(encrypted_value=reencrypt(token))
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Re-encrypted {count} values. You can now remove the old key."))
