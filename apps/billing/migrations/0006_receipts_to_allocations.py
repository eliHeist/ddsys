"""Existing receipts: their client and project come from their invoice, and each gets the allocation that says
it paid that invoice. Invoice paid amounts don't change (they were the receipts' totals; now the allocations')."""
from django.db import migrations


def forwards(apps, schema_editor):
    Receipt = apps.get_model("billing", "Receipt")
    Allocation = apps.get_model("billing", "Allocation")
    for receipt in Receipt.objects.select_related("invoice"):
        receipt.client_id, receipt.project_id = receipt.invoice.client_id, receipt.invoice.project_id
        receipt.quotation_id = receipt.invoice.quotation_id
        receipt.save(update_fields=["client", "project", "quotation"])
        Allocation.objects.create(receipt=receipt, invoice_id=receipt.invoice_id, amount=receipt.amount, date=receipt.date,
                                  created_by_id=receipt.received_by_id)


def backwards(apps, schema_editor):
    apps.get_model("billing", "Allocation").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("billing", "0005_client_credit")]
    operations = [migrations.RunPython(forwards, backwards)]
